# StoreKit Reference (In-App Purchases & Subscriptions)

Comprehensive guide to monetization on Apple platforms using StoreKit 2. Covers product loading, purchase flows, transaction management, subscriptions, StoreKit SwiftUI views, testing, and server-side verification. StoreKit 2 is the modern Swift-native API (iOS 15+) — do not use the original StoreKit API for new code.

## Architecture Overview

| Component | Purpose |
|---|---|
| **Product** | Load product info from App Store, initiate purchases |
| **Transaction** | Verify purchases, manage entitlements, listen for updates |
| **SubscriptionStoreView** | SwiftUI view for merchandising subscriptions (iOS 17+) |
| **StoreView** / **ProductView** | SwiftUI views for merchandising any product type (iOS 17+) |
| **AppTransaction** | Verify the app itself was legitimately purchased |
| **StoreKit Configuration File** | Local testing in Xcode without App Store Connect |

## Product Types

| Type | Behavior | Example |
|---|---|---|
| **Consumable** | Can be purchased multiple times, depletes | Gems, coins, extra lives |
| **Non-consumable** | One-time permanent purchase | Remove ads, premium features |
| **Auto-renewable subscription** | Recurring billing, automatic renewal | Monthly/yearly plans |
| **Non-renewing subscription** | Fixed duration, no auto-renewal | Season pass, 30-day access |


## Loading Products

```swift
import StoreKit

// Define product identifiers (match App Store Connect or StoreKit config file)
enum ProductID {
    static let premium = "com.example.app.premium"
    static let monthlyPlan = "com.example.app.monthly"
    static let yearlyPlan = "com.example.app.yearly"
    static let coins100 = "com.example.app.coins.100"

    static let all = [premium, monthlyPlan, yearlyPlan, coins100]
}

// Load products
let products = try await Product.products(for: ProductID.all)

for product in products {
    print("\(product.displayName): \(product.displayPrice)")
    print("Type: \(product.type)")  // .consumable, .nonConsumable, .autoRenewable, .nonRenewing
}
```

Key `Product` properties:
- `id` — unique product identifier string
- `displayName` — localized name
- `description` — localized description
- `displayPrice` — localized price string (e.g., "$9.99")
- `price` — `Decimal` value
- `type` — `Product.ProductType`
- `subscription` — `Product.SubscriptionInfo?` (nil for non-subscriptions)
- `isFamilyShareable` — Family Sharing support


## Purchase Flow
---

```swift
func purchase(_ product: Product) async throws {
    let result = try await product.purchase()

    switch result {
    case .success(let verification):
        // Verify the transaction
        switch verification {
        case .verified(let transaction):
            // Deliver content
            await deliverContent(for: transaction)
            // MUST call finish() after delivering content
            await transaction.finish()

        case .unverified(let transaction, let error):
            // Transaction failed verification — handle cautiously
            print("Unverified transaction: \(error)")
        }

    case .userCancelled:
        // User dismissed the purchase sheet
        break

    case .pending:
        // Transaction is pending (e.g., Ask to Buy, SCA)
        // Will arrive later via Transaction.updates
        break

    @unknown default:
        break
    }
}
```

#### Purchase Options

```swift
// Associate purchase with your user account (for server-side tracking)
let result = try await product.purchase(options: [
    .appAccountToken(UUID(uuidString: userAccountID)!)
])

// Promotional offer
let result = try await product.purchase(options: [
    .promotionalOffer(offerID: "SPRING_SALE", keyID: keyID, nonce: nonce, signature: signature, timestamp: timestamp)
])
```

#### Purchase with Confirmation Scene (iOS 17+)

```swift
// Specify where to present the purchase confirmation
let result = try await product.purchase(confirmIn: windowScene)
```


## Transaction Management
---

### Transaction Listener

**Start at app launch** — catches purchases made outside the app (other device, App Store, subscription renewals):

```swift
@main
struct MyApp: App {
    @State private var store = StoreManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(store)
                .task {
                    await store.listenForTransactions()
                }
        }
    }
}

@Observable
class StoreManager {
    private var updateListenerTask: Task<Void, Never>?

    func listenForTransactions() async {
        for await result in Transaction.updates {
            guard case .verified(let transaction) = result else { continue }
            await handleVerifiedTransaction(transaction)
            await transaction.finish()
        }
    }
}
```

### Current Entitlements

Determine what content the user has access to:

```swift
func updateEntitlements() async {
    var activeProductIDs: Set<String> = []

    for await result in Transaction.currentEntitlements {
        guard case .verified(let transaction) = result else { continue }

        switch transaction.productType {
        case .nonConsumable, .autoRenewable:
            if transaction.revocationDate == nil {
                activeProductIDs.insert(transaction.productID)
            }
        default:
            break
        }
    }

    self.purchasedProductIDs = activeProductIDs
}
```

### Restore Purchases

StoreKit 2 handles this automatically via `Transaction.currentEntitlements`. For explicit restore (e.g., a "Restore Purchases" button):

```swift
func restorePurchases() async {
    try? await AppStore.sync()  // Forces sync with App Store
    await updateEntitlements()
}
```

### Finishing Transactions

**Always call `transaction.finish()`** after delivering content. Unfinished transactions:
- Reappear in `Transaction.unfinished`
- Block new purchases of the same product (non-consumables)
- Indicate undelivered content to the App Store

```swift
// Process any unfinished transactions on launch
func processUnfinishedTransactions() async {
    for await result in Transaction.unfinished {
        guard case .verified(let transaction) = result else { continue }
        await deliverContent(for: transaction)
        await transaction.finish()
    }
}
```


## Subscriptions
---

### Checking Subscription Status

```swift
func checkSubscriptionStatus() async throws -> Bool {
    guard let product = try await Product.products(for: [ProductID.monthlyPlan]).first,
          let subscription = product.subscription
    else { return false }

    let statuses = try await subscription.status

    for status in statuses {
        guard case .verified(let renewalInfo) = status.renewalInfo,
              case .verified(let transaction) = status.transaction
        else { continue }

        switch status.state {
        case .subscribed:
            // Active subscription
            return true
        case .expired:
            // Check expiration reason
            if let expirationReason = renewalInfo.expirationReason {
                handleExpiration(expirationReason)
            }
        case .revoked:
            // Refunded or revoked
            break
        case .inBillingRetryPeriod:
            // Payment failed, Apple is retrying
            // Consider giving limited access
            break
        case .inGracePeriod:
            // Payment failed but within grace period — maintain access
            return true
        default:
            break
        }
    }
    return false
}
```

### Subscription Renewal Info

```swift
// From verified renewalInfo
let willAutoRenew = renewalInfo.willAutoRenew
let currentProductID = renewalInfo.currentProductID
let autoRenewPreference = renewalInfo.autoRenewPreference  // Product they'll renew to
let expirationReason = renewalInfo.expirationReason
let gracePeriodExpirationDate = renewalInfo.gracePeriodExpirationDate
```

### Subscription Offers
---

Four types of offers exist. Each targets a different audience and has different configuration/redemption flows.

| Offer Type | Target Audience | Payment Modes | Requires Signature | Configuration |
|---|---|---|---|---|
| **Introductory** | First-time subscribers only | Free trial, pay as you go, pay up front | No | App Store Connect |
| **Promotional** | Existing or lapsed subscribers | Free trial, pay as you go, pay up front | Yes (server-side) | App Store Connect + server |
| **Win-back** | Lapsed subscribers | Free trial, pay as you go, pay up front | No | App Store Connect |
| **Offer codes** | Anyone with a code | Free or discounted | No | App Store Connect (up to 10 active, 1M codes/quarter) |

#### Payment Modes

| Mode | Behavior | Example |
|---|---|---|
| `.freeTrial` | No charge during offer period | "7-day free trial" |
| `.payAsYouGo` | Discounted recurring rate for N periods | "$0.99/month for 3 months" |
| `.payUpFront` | Single discounted payment for the entire offer period | "$9.99 for 6 months" |

#### Accessing Offers on a Product

```swift
guard let subscription = product.subscription else { return }

// Introductory offer (only one per subscription group)
if let introOffer = subscription.introductoryOffer {
    print("Intro: \(introOffer.displayPrice) - \(introOffer.paymentMode)")
    print("Period: \(introOffer.period) x \(introOffer.periodCount)")
}

// Promotional offers (configured in App Store Connect)
for offer in subscription.promotionalOffers {
    print("Promo: \(offer.id ?? "") - \(offer.displayPrice)")
}

// Win-back offers (iOS 18+)
for offer in subscription.winBackOffers {
    print("Win-back: \(offer.id ?? "") - \(offer.displayPrice)")
}
```

#### Introductory Offer Eligibility

A user is eligible only if they have never subscribed to any product in the subscription group:

```swift
let isEligible = await product.subscription?.isEligibleForIntroOffer ?? false

if isEligible, let introOffer = product.subscription?.introductoryOffer {
    switch introOffer.paymentMode {
    case .freeTrial:
        showBanner("Start your \(introOffer.period) free trial")
    case .payAsYouGo:
        showBanner("\(introOffer.displayPrice)/\(introOffer.period) for \(introOffer.periodCount) periods")
    case .payUpFront:
        showBanner("\(introOffer.displayPrice) for \(introOffer.periodCount) \(introOffer.period)s")
    default:
        break
    }
}
```

#### Promotional Offers (Server-Signed)

Require a server-generated signature. Used to retain existing subscribers or win back lapsed ones with targeted deals:

```swift
// 1. Request signature from your server
let signatureData = try await yourServer.generateOfferSignature(
    productID: product.id,
    offerID: "SPRING_SALE",
    appAccountToken: userID
)

// 2. Purchase with promotional offer
let result = try await product.purchase(options: [
    .promotionalOffer(
        offerID: signatureData.offerID,
        keyID: signatureData.keyID,
        nonce: signatureData.nonce,
        signature: signatureData.signature,
        timestamp: signatureData.timestamp
    )
])
```

#### Win-Back Offers (iOS 18+)

Automatically offered to lapsed subscribers. No server signature needed — Apple determines eligibility:

```swift
// Check win-back offer availability
if let winBackOffers = product.subscription?.winBackOffers, !winBackOffers.isEmpty {
    // Show win-back UI
    for offer in winBackOffers {
        print("Come back: \(offer.displayPrice) for \(offer.period)")
    }
}

// SubscriptionStoreView handles win-back offers automatically
SubscriptionStoreView(groupID: groupID)
    // Win-back offers are displayed to eligible users without additional code
```

#### Offer Codes

Alphanumeric codes distributed outside the app (email campaigns, social media, partnerships). Available for all product types (iOS 16.3+ for non-subscriptions):

```swift
// Present the redemption sheet
// SwiftUI
.offerCodeRedemption(isPresented: $showRedeemSheet) { result in
    // Transaction arrives via Transaction.updates
}

// UIKit
try await AppStore.presentOfferCodeRedeemSheet(in: windowScene)
```

Identifying offer code transactions:

```swift
if let offer = transaction.offer, offer.type == .code {
    // This transaction came from an offer code redemption
}
```

### Manage Subscriptions

Open the system subscription management sheet:

```swift
// SwiftUI
.manageSubscriptionsSheet(isPresented: $showManageSubscriptions)

// Programmatic
try await AppStore.showManageSubscriptions(in: windowScene)
```


## StoreKit SwiftUI Views (iOS 17+)
---

Pre-built views for merchandising — no custom UI needed for standard storefronts.

### SubscriptionStoreView

Displays auto-renewable subscription options for a subscription group:

```swift
import StoreKit

struct PaywallView: View {
    var body: some View {
        SubscriptionStoreView(groupID: "YOUR_SUBSCRIPTION_GROUP_ID") {
            // Custom marketing content (header)
            VStack(spacing: 12) {
                Image(systemName: "crown.fill")
                    .font(.system(size: 60))
                    .foregroundStyle(.yellow)
                Text("Unlock Premium")
                    .font(.title.bold())
                Text("Get unlimited access to all features")
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
        .storeButton(.visible, for: .restorePurchases)
        .storeButton(.hidden, for: .cancellation)
        .subscriptionStoreControlStyle(.prominentPicker)
    }
}
```

#### Customization

```swift
SubscriptionStoreView(groupID: groupID)
    // Control which subscription tiers to show
    // .visibleRelationships: .upgrade — show only upgrades from current plan
    .subscriptionStoreControlStyle(.prominentPicker)

    // Policy links
    .subscriptionStorePolicyDestination(url: termsURL, for: .termsOfService)
    .subscriptionStorePolicyDestination(url: privacyURL, for: .privacyPolicy)

    // Sign-in action
    .subscriptionStoreSignInAction {
        showSignIn = true
    }

    // Background
    .containerBackground(.blue.gradient, for: .subscriptionStoreHeader)
```

### StoreView

Displays a grid of any product type:

```swift
struct ShopView: View {
    var body: some View {
        StoreView(ids: ProductID.all)
            .storeButton(.visible, for: .restorePurchases)
            .productViewStyle(.regular)
    }
}
```

### ProductView

Merchandises a single product:

```swift
ProductView(id: ProductID.premium) {
    // Custom icon
    Image(systemName: "star.fill")
        .font(.title)
}
```


## Verification
---

StoreKit 2 wraps transactions in `VerificationResult<Transaction>`. The App Store signs transactions in JWS (JSON Web Signature) format.

### On-Device Verification (Default)

StoreKit automatically verifies the signature. Handle both cases:

```swift
func handleVerification<T>(_ result: VerificationResult<T>) throws -> T {
    switch result {
    case .verified(let value):
        return value
    case .unverified(_, let error):
        throw StoreError.verificationFailed(error)
    }
}
```

### Server-Side Verification

For additional security, verify transactions on your server using the App Store Server API:

```swift
// Get JWS representation for server validation
let jwsRepresentation = verificationResult.jwsRepresentation
// Send to your server for verification against Apple's public key
```

### AppTransaction (App Purchase Verification)

Verify the app itself was legitimately purchased (anti-piracy):

```swift
let appTransaction = try await AppTransaction.shared
switch appTransaction {
case .verified(let transaction):
    // App was legitimately purchased
    let originalPurchaseDate = transaction.originalPurchaseDate
case .unverified(_, let error):
    // Verification failed — handle accordingly
    break
}
```


## Refund Requests
---

```swift
// Present refund request UI
let status = try await Transaction.beginRefundRequest(
    for: transaction.id,
    in: windowScene
)

switch status {
case .success:
    // Refund request submitted
    break
case .userCancelled:
    // User cancelled the refund request
    break
@unknown default:
    break
}
```


## Testing
---

### StoreKit Configuration File (Xcode)

1. File → New → StoreKit Configuration File
2. Add products matching your App Store Connect setup
3. Scheme → Edit Scheme → Run → Options → StoreKit Configuration → select file
4. Test purchases locally — no sandbox account needed

```swift
// Products load from the config file during testing
let products = try await Product.products(for: ProductID.all)
// Purchases complete immediately without payment
```

### Sandbox Testing

For testing with real App Store infrastructure:
1. Create sandbox tester in App Store Connect → Users and Access → Sandbox Testers
2. Sign in with sandbox account on device (Settings → App Store → Sandbox Account)
3. Purchases are free but follow real purchase flows

### Transaction Manager (Xcode)

Debug → StoreKit → Manage Transactions — lets you:
- View all transactions
- Delete transactions
- Refund transactions
- Expire subscriptions
- Trigger Ask to Buy approval/rejection

### Testing Specific Scenarios

```swift
// Simulate Ask to Buy (sandbox)
let result = try await product.purchase(options: [
    .simulatesAskToBuyInSandbox(true)
])

// Test subscription renewal by setting short renewal periods in StoreKit config
```


## Complete Store Implementation
---

```swift
@Observable
class StoreManager {
    private(set) var products: [Product] = []
    private(set) var purchasedProductIDs: Set<String> = []
    private var updateListenerTask: Task<Void, Never>?

    var isPremium: Bool {
        purchasedProductIDs.contains(ProductID.premium) ||
        purchasedProductIDs.contains(ProductID.monthlyPlan) ||
        purchasedProductIDs.contains(ProductID.yearlyPlan)
    }

    init() {
        updateListenerTask = Task { await listenForTransactions() }
        Task { await loadProducts() }
        Task { await updateEntitlements() }
    }

    deinit {
        updateListenerTask?.cancel()
    }

    func loadProducts() async {
        do {
            products = try await Product.products(for: ProductID.all)
                .sorted { $0.price < $1.price }
        } catch {
            print("Failed to load products: \(error)")
        }
    }

    func purchase(_ product: Product) async throws -> Bool {
        let result = try await product.purchase()

        switch result {
        case .success(let verification):
            guard case .verified(let transaction) = verification else { return false }
            await transaction.finish()
            await updateEntitlements()
            return true
        case .userCancelled, .pending:
            return false
        @unknown default:
            return false
        }
    }

    func updateEntitlements() async {
        var ids: Set<String> = []
        for await result in Transaction.currentEntitlements {
            guard case .verified(let transaction) = result,
                  transaction.revocationDate == nil
            else { continue }
            ids.insert(transaction.productID)
        }
        purchasedProductIDs = ids
    }

    private func listenForTransactions() async {
        for await result in Transaction.updates {
            guard case .verified(let transaction) = result else { continue }
            await transaction.finish()
            await updateEntitlements()
        }
    }
}
```


## Common Pitfalls

| Pitfall | Fix |
|---|---|
| Not calling `transaction.finish()` | Unfinished transactions block future purchases and reappear in `unfinished`. Always finish after delivering content |
| Not listening for `Transaction.updates` | Misses purchases from other devices, subscription renewals, offer redemptions. Start listener at app launch |
| Checking entitlements only at purchase time | Use `Transaction.currentEntitlements` on every app launch to handle renewals, expirations, revocations |
| Not handling `.pending` purchase result | Ask to Buy and SCA require deferred handling — the transaction arrives later via `Transaction.updates` |
| Using original StoreKit API in new code | StoreKit 2 is simpler, safer, and actively developed. Original API is effectively legacy |
| Hardcoding prices | Always use `product.displayPrice` — it's localized and currency-aware |
| Not handling `.unverified` transactions | Decide a policy: reject, log, or accept with caution. Never silently ignore verification failures |
| Testing only with StoreKit config file | Also test in sandbox with real App Store infrastructure before release |
| Not syncing on "Restore Purchases" | Call `AppStore.sync()` then re-check `Transaction.currentEntitlements` |
| Missing subscription grace period handling | Users in `.inGracePeriod` should retain access — Apple is retrying payment |
| Not checking `revocationDate` | Revoked/refunded transactions should remove access. Always filter by `revocationDate == nil` |
