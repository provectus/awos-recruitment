# Billing & Payments Reference

Covers Google Play Billing Library integration for in-app purchases and subscriptions. Includes one-time products (consumable and non-consumable), subscription lifecycle management, purchase verification, alternative billing, and testing. For Amazon IAP on Fire TV, see `fire-tv-patterns.md`.

## Contents
- Setup — Gradle dependencies, BillingClient initialization, connection management
- Querying Products — ProductDetails, offer tokens, billing config
- One-Time Purchases — consumable vs non-consumable, purchase flow, acknowledge, consume
- Subscriptions — base plans, offers, replacement modes, lifecycle states
  - Subscription Offers — eligibility types (new customer, upgrade, developer-determined), pricing phases, offer tags, client-side filtering, winback offers, promo codes
- Purchase Verification & Security — backend validation, purchase token, signature
- Subscription Lifecycle — grace period, account hold, pause, resubscribe, cancellation
- Alternative Billing — user choice billing, external offers
- Testing — license testers, Play Billing Lab, test instruments, subscription acceleration
- Common Pitfalls — acknowledgement window, pending purchases, caching


## Setup

Google Play Billing Library (PBL) is the only supported way to sell digital goods on Google Play. Current major version is **PBL 8** (artifact `com.android.billingclient:billing`). PBL 7 remains supported until August 31, 2026.

### Gradle Setup

```kotlin
// libs.versions.toml
[versions]
billing = "<latest>" // PBL 8.x

[libraries]
billing = { module = "com.android.billingclient:billing", version.ref = "billing" }
billing-ktx = { module = "com.android.billingclient:billing-ktx", version.ref = "billing" }
```

```kotlin
// build.gradle.kts (app or :core:billing module)
dependencies {
    implementation(libs.billing)      // core library
    implementation(libs.billing.ktx)  // Kotlin coroutine extensions (recommended)
}
```

> **Note:** `billing-ktx` adds `suspend` wrappers (`queryProductDetails`, `acknowledgePurchase`, `consumePurchase`) so you can call them from coroutines instead of using async callbacks.

### BillingClient Initialization

```kotlin
class BillingManager(
    private val context: Context,
) {
    private val _purchases = MutableStateFlow<List<Purchase>>(emptyList())
    val purchases: StateFlow<List<Purchase>> = _purchases.asStateFlow()

    private val purchasesUpdatedListener = PurchasesUpdatedListener { billingResult, purchases ->
        when (billingResult.responseCode) {
            BillingResponseCode.OK -> {
                purchases?.let { _purchases.value = it }
            }
            BillingResponseCode.USER_CANCELED -> { /* user backed out */ }
            else -> { /* log billingResult.debugMessage */ }
        }
    }

    val billingClient: BillingClient = BillingClient.newBuilder(context)
        .setListener(purchasesUpdatedListener)
        .enablePendingPurchases()              // required since PBL 5
        .enableAutoServiceReconnection()       // PBL 8+ — handles reconnection automatically
        .build()
}
```

### Connecting to Google Play

```kotlin
billingClient.startConnection(object : BillingClientStateListener {
    override fun onBillingSetupFinished(billingResult: BillingResult) {
        if (billingResult.responseCode == BillingResponseCode.OK) {
            // Ready — query products, restore purchases, etc.
        }
    }

    override fun onBillingServiceDisconnected() {
        // No-op when enableAutoServiceReconnection() is used.
        // Otherwise: retry with exponential backoff.
    }
})
```

**Rules:**
- Call `enablePendingPurchases()` — required for all apps.
- Call `enableAutoServiceReconnection()` (PBL 8+) to avoid manual reconnection logic.
- Create one `BillingClient` per app process. Do not create multiple instances.
- End the connection with `billingClient.endConnection()` when the billing manager is no longer needed.


## Querying Products

Products are configured in the Google Play Console. Query them at runtime to get localized pricing and offer details.

```kotlin
suspend fun queryProducts(
    productIds: List<String>,
    productType: String = BillingClient.ProductType.INAPP,
): List<ProductDetails> {
    val productList = productIds.map { id ->
        QueryProductDetailsParams.Product.newBuilder()
            .setProductId(id)
            .setProductType(productType)
            .build()
    }
    val params = QueryProductDetailsParams.newBuilder()
        .setProductList(productList)
        .build()

    val result = billingClient.queryProductDetails(params) // suspend (ktx)
    return if (result.billingResult.responseCode == BillingResponseCode.OK) {
        result.productDetailsList.orEmpty()
    } else {
        emptyList()
    }
}
```

**Rules:**
- Query products every time the purchase UI is displayed — do not cache `ProductDetails` long-term; stale tokens cause `launchBillingFlow` failures.
- Use `ProductType.INAPP` for one-time products, `ProductType.SUBS` for subscriptions.
- Check `getUnfetchedProductList()` on the result to detect products that could not be fetched (misconfigured in Console, wrong product type, etc.).

### Getting Billing Country

```kotlin
val configParams = GetBillingConfigParams.newBuilder().build()
billingClient.getBillingConfigAsync(configParams) { billingResult, billingConfig ->
    if (billingResult.responseCode == BillingResponseCode.OK && billingConfig != null) {
        val countryCode = billingConfig.countryCode // ISO 3166-1 alpha-2
    }
}
```


## One-Time Purchases

Two types of one-time (in-app) products:

| Type | Behavior | After Purchase |
|------|----------|----------------|
| **Non-consumable** | Purchased once, owned permanently | Acknowledge |
| **Consumable** | Can be purchased repeatedly (coins, gems) | Consume (implicitly acknowledges) |

### Launching the Purchase Flow

```kotlin
fun launchPurchase(activity: Activity, productDetails: ProductDetails) {
    val params = BillingFlowParams.newBuilder()
        .setProductDetailsParamsList(
            listOf(
                BillingFlowParams.ProductDetailsParams.newBuilder()
                    .setProductDetails(productDetails)
                    .build()
            )
        )
        .build()

    billingClient.launchBillingFlow(activity, params)
    // Result arrives in PurchasesUpdatedListener
}
```

### Processing Purchases

```kotlin
suspend fun handlePurchase(purchase: Purchase) {
    // 1. Verify on secure backend (see Purchase Verification section)
    val isVerified = backendApi.verifyPurchase(
        purchaseToken = purchase.purchaseToken,
        productId = purchase.products.first(),
    )
    if (!isVerified) return

    // 2. Check purchase state
    if (purchase.purchaseState != Purchase.PurchaseState.PURCHASED) return // PENDING — wait

    // 3. Grant entitlement
    grantAccess(purchase.products)

    // 4. Acknowledge or consume
    if (isConsumable(purchase)) {
        consumePurchase(purchase)
    } else {
        acknowledgePurchase(purchase)
    }
}
```

### Acknowledging (Non-Consumable)

```kotlin
suspend fun acknowledgePurchase(purchase: Purchase) {
    if (purchase.isAcknowledged) return
    val params = AcknowledgePurchaseParams.newBuilder()
        .setPurchaseToken(purchase.purchaseToken)
        .build()
    val result = billingClient.acknowledgePurchase(params)
    if (result.responseCode != BillingResponseCode.OK) {
        // Retry — unacknowledged purchases are refunded after 3 days
    }
}
```

### Consuming (Consumable)

```kotlin
suspend fun consumePurchase(purchase: Purchase) {
    val params = ConsumeParams.newBuilder()
        .setPurchaseToken(purchase.purchaseToken)
        .build()
    val result = billingClient.consumePurchase(params)
    if (result.billingResult.responseCode == BillingResponseCode.OK) {
        // Product is available for purchase again
    }
}
```

### Restoring Purchases

Query purchases on every app launch to restore entitlements:

```kotlin
suspend fun restorePurchases() {
    val params = QueryPurchasesParams.newBuilder()
        .setProductType(BillingClient.ProductType.INAPP)
        .build()
    val result = billingClient.queryPurchasesAsync(params)
    if (result.billingResult.responseCode == BillingResponseCode.OK) {
        for (purchase in result.purchasesList) {
            if (purchase.purchaseState == Purchase.PurchaseState.PURCHASED) {
                grantAccess(purchase.products)
                if (!purchase.isAcknowledged) acknowledgePurchase(purchase)
            }
        }
    }
}
```

**Rules:**
- Acknowledge non-consumable purchases within **3 days** or Google auto-refunds them.
- Consume consumable purchases as soon as you deliver the item — consumption implicitly acknowledges.
- Always check `purchaseState == PURCHASED` before granting access — `PENDING` means payment is not yet complete.
- Call `queryPurchasesAsync` on every app launch and after `onResume` to catch purchases made outside the app (promo codes, Play Store).


## Subscriptions

### Key Concepts

| Term | Description |
|------|-------------|
| **Product** | A subscription defined in Play Console (e.g., "premium") |
| **Base plan** | A pricing configuration for the product (e.g., monthly, annual) |
| **Offer** | Discounted pricing attached to a base plan (free trial, intro price) |
| **Offer token** | Opaque string identifying a specific base-plan + offer combination |
| **Prepaid plan** | Does not auto-renew; user "tops up" to extend |

### Querying Subscription Offers

```kotlin
suspend fun querySubscriptions(): List<ProductDetails> =
    queryProducts(listOf("premium", "premium_family"), BillingClient.ProductType.SUBS)

// Each ProductDetails has subscriptionOfferDetails — a list of base plan + offer combos
fun getOffers(productDetails: ProductDetails): List<ProductDetails.SubscriptionOfferDetails> =
    productDetails.subscriptionOfferDetails.orEmpty()

// Display pricing from the offer
fun formatPrice(offer: ProductDetails.SubscriptionOfferDetails): String {
    val phase = offer.pricingPhases.pricingPhaseList.last() // last phase = recurring price
    return "${phase.formattedPrice} / ${phase.billingPeriod}" // e.g., "$4.99 / P1M"
}
```

### Subscription Offers — Types, Eligibility & Pricing Phases

Offers are configured in Google Play Console and attached to base plans. Each base plan can have multiple offers. The client receives all eligible offers via `subscriptionOfferDetails`.

#### Offer Eligibility Types

| Eligibility | Who Qualifies | Enforcement |
|-------------|---------------|-------------|
| **New customer acquisition** | Users who have never subscribed to this product (or to any product in the app — configurable) | Google Play enforces automatically; ineligible users won't see the offer |
| **Upgrade** | Existing subscribers moving from a lower tier to a higher one | Google Play enforces based on configured source products |
| **Developer-determined** | Anyone — you decide eligibility in your app logic | Google Play always returns these offers; your code must filter |

#### Pricing Phases

Each offer has up to **two discounted phases** followed by the regular recurring phase of the base plan. Phases execute in order.

| Phase Type | Duration | Example |
|------------|----------|---------|
| **Free** | Fixed period | 7-day free trial |
| **Single payment** | Fixed period, one charge | $0.99 for first month |
| **Discounted recurring** | Fixed number of billing periods at reduced price | $2.99/mo for 3 months |
| **Regular recurring** | Indefinite (from the base plan) | $9.99/mo |

```kotlin
// Inspect pricing phases of an offer
fun describePricingPhases(offer: ProductDetails.SubscriptionOfferDetails): List<String> =
    offer.pricingPhases.pricingPhaseList.map { phase ->
        buildString {
            append(phase.formattedPrice)
            append(" / ${phase.billingPeriod}")   // ISO 8601 duration: P1W, P1M, P3M, P1Y
            append(" × ${phase.billingCycleCount}") // 0 = infinite (recurring)
            append(" (recurrence: ${phase.recurrenceMode})") // 1=INFINITE, 2=FINITE, 3=NON_RECURRING
        }
    }

// recurrenceMode values:
// RecurrenceMode.INFINITE_RECURRING (1) — base plan recurring price
// RecurrenceMode.FINITE_RECURRING (2)   — discounted recurring (e.g., 3 months at intro price)
// RecurrenceMode.NON_RECURRING (3)      — single payment or free trial
```

#### Offer Tags

Tags are arbitrary strings you assign to offers in Play Console (e.g., `"seasonal-sale"`, `"winback"`, `"tier-upgrade"`). Use them to filter and select the right offer client-side.

```kotlin
// Filter offers by tag
fun findOfferByTag(
    productDetails: ProductDetails,
    tag: String,
): ProductDetails.SubscriptionOfferDetails? =
    productDetails.subscriptionOfferDetails?.firstOrNull { offer ->
        tag in offer.offerTags
    }

// Select the best offer for a user
fun selectOffer(
    productDetails: ProductDetails,
    isReturningUser: Boolean,
): ProductDetails.SubscriptionOfferDetails? {
    val offers = productDetails.subscriptionOfferDetails.orEmpty()

    // 1. Check for developer-determined winback offer
    if (isReturningUser) {
        val winback = offers.firstOrNull { "winback" in it.offerTags }
        if (winback != null) return winback
    }

    // 2. Fall back to the cheapest offer (longest free trial or lowest intro price)
    val bestIntro = offers
        .filter { it.pricingPhases.pricingPhaseList.any { p -> p.priceAmountMicros == 0L } }
        .maxByOrNull { offer ->
            // Prefer the longest free phase
            offer.pricingPhases.pricingPhaseList
                .filter { it.priceAmountMicros == 0L }
                .sumOf { it.billingCycleCount }
        }
    if (bestIntro != null) return bestIntro

    // 3. Fall back to base plan (no offer)
    return offers.firstOrNull { it.pricingPhases.pricingPhaseList.size == 1 }
}
```

#### Developer-Determined Offers

Google Play **always** returns these in `subscriptionOfferDetails` regardless of user state. Your app must:
1. Decide if the user qualifies (e.g., check backend for past subscription history, loyalty status).
2. Show or hide the offer accordingly.
3. Pass the correct `offerToken` to `launchBillingFlow`.

Use offer tags to distinguish developer-determined offers from Play-enforced ones.

#### Winback Offers

Target users who previously subscribed but canceled or let their subscription expire.

- Configure as **developer-determined** eligibility in Play Console.
- Tag with `"winback"` (or your own convention) for easy client-side filtering.
- Check on your backend whether the user is a past subscriber before presenting the offer.
- Launch the purchase flow with the winback offer's `offerToken` — same API as a new subscription.

#### Promo Codes

One-time promotional codes created in Play Console:
- **One-time use** — auto-generated, unique per code, redeemable once. Limit: 500/quarter (one-time products) or 10,000/quarter (subscriptions).
- **Custom codes** — developer-specified string, multiple redemptions (2,000–99,999 limit). Subscriptions only, new subscribers only.

Promo codes provide a **free trial**, not a free subscription. Users redeem via:
- In-app purchase dialog → "Redeem"
- Google Play Store → "Redeem code"
- Deep link: `https://play.google.com/redeem?code=YOUR_CODE`

After redemption, the purchase appears in `queryPurchasesAsync` and must be acknowledged normally.

### Launching a Subscription Purchase

```kotlin
fun launchSubscription(
    activity: Activity,
    productDetails: ProductDetails,
    offerToken: String,
) {
    val params = BillingFlowParams.newBuilder()
        .setProductDetailsParamsList(
            listOf(
                BillingFlowParams.ProductDetailsParams.newBuilder()
                    .setProductDetails(productDetails)
                    .setOfferToken(offerToken)
                    .build()
            )
        )
        .build()
    billingClient.launchBillingFlow(activity, params)
}
```

### Upgrade / Downgrade (Replacement)

```kotlin
fun launchUpgrade(
    activity: Activity,
    newProductDetails: ProductDetails,
    newOfferToken: String,
    oldPurchaseToken: String,
    replacementMode: Int = BillingFlowParams.ReplacementMode.CHARGE_PRORATED_PRICE,
) {
    val params = BillingFlowParams.newBuilder()
        .setProductDetailsParamsList(
            listOf(
                BillingFlowParams.ProductDetailsParams.newBuilder()
                    .setProductDetails(newProductDetails)
                    .setOfferToken(newOfferToken)
                    .build()
            )
        )
        .setSubscriptionUpdateParams(
            BillingFlowParams.SubscriptionUpdateParams.newBuilder()
                .setOldPurchaseToken(oldPurchaseToken)
                .setSubscriptionReplacementMode(replacementMode)
                .build()
        )
        .build()
    billingClient.launchBillingFlow(activity, params)
}
```

### Replacement Modes

| Mode | When to Use | Billing Effect |
|------|-------------|----------------|
| `WITH_TIME_PRORATION` | Upgrade immediately, adjust remaining time | Immediate charge, renewal date shifts |
| `CHARGE_PRORATED_PRICE` | Upgrade immediately, keep billing date | Prorated charge for remaining period |
| `CHARGE_FULL_PRICE` | Upgrade immediately, charge full price | Full charge, credit extends next renewal |
| `WITHOUT_PRORATION` | Upgrade immediately, no charge until renewal | Free until next billing date |
| `DEFERRED` | Downgrade at next renewal | No immediate charge, change at renewal |

**Recommendations:**
- **Upgrade to more expensive tier** → `CHARGE_PRORATED_PRICE`
- **Downgrade to cheaper tier** → `DEFERRED`
- **Upgrade during free trial (keep trial)** → `WITHOUT_PRORATION`
- **Switch to prepaid from any plan** → `CHARGE_FULL_PRICE` (only mode allowed)

### Handling Replacement Purchases

```kotlin
// In PurchasesUpdatedListener — replacement creates a new Purchase
fun handleSubscriptionPurchase(purchase: Purchase) {
    // Invalidate old token if this is a replacement
    val linkedToken = purchase.linkedPurchaseToken
    if (linkedToken != null) {
        // Revoke entitlement for old token on your backend
        backendApi.invalidateToken(linkedToken)
    }

    // Process new purchase normally
    verifyAndAcknowledge(purchase)
}
```

### Installment Subscriptions (PBL 7+)

Available in Brazil, France, Italy, Spain. Users pay monthly over a commitment period.

```kotlin
// Check installment details on the offer
val offer: ProductDetails.SubscriptionOfferDetails = ...
val installmentDetails = offer.installmentPlanDetails
if (installmentDetails != null) {
    val commitmentPayments = installmentDetails.installmentPlanCommitmentPaymentsCount
    val renewalPayments = installmentDetails.subsequentInstallmentPlanCommitmentPaymentsCount
}
```


## Purchase Verification & Security

**Always verify purchases on a secure backend.** Client-side verification alone is not sufficient — it can be bypassed.

### Verification Flow

```
App → Purchase → purchaseToken → Your Backend → Google Play Developer API → Verified ✓
                                                                          → Rejected ✗
```

### Backend Verification (Google Play Developer API)

```
# One-time product
GET https://androidpublisher.googleapis.com/androidpublisher/v3/
    applications/{packageName}/purchases/products/{productId}/tokens/{token}

# Subscription (v2)
GET https://androidpublisher.googleapis.com/androidpublisher/v3/
    applications/{packageName}/purchases/subscriptionsv2/tokens/{token}
```

### Real-Time Developer Notifications (RTDN)

Enable in Play Console to receive push notifications for purchase state changes:

- `ONE_TIME_PRODUCT_PURCHASED` — process purchase
- `ONE_TIME_PRODUCT_CANCELED` — revoke access
- `SUBSCRIPTION_PURCHASED` — activate subscription
- `SUBSCRIPTION_RENEWED` — extend entitlement
- `SUBSCRIPTION_CANCELED` — mark for expiration
- `SUBSCRIPTION_REVOKED` — revoke access immediately
- `SUBSCRIPTION_ON_HOLD` — suspend access
- `SUBSCRIPTION_IN_GRACE_PERIOD` — keep access, prompt payment fix
- `SUBSCRIPTION_PAUSED` — suspend access
- `SUBSCRIPTION_RESTARTED` — reactivate

**Rules:**
- Use `obfuscatedAccountId` / `obfuscatedProfileId` in `BillingFlowParams` to link purchases to your user accounts.
- Never rely solely on client-side purchase state — always confirm with backend.
- Store purchase tokens on your backend to detect duplicate or replayed tokens.
- Enable RTDNs — they are critical for keeping entitlement state in sync with Google Play.


## Subscription Lifecycle

### State Machine

```
Purchase → Active → (Grace Period) → (Account Hold) → Expired
                  → Paused → Resumed → Active
                  → Canceled → Expired
```

### Grace Period

- Configured per base plan in Play Console (typically 3–7 days).
- User **retains access** while Google retries payment.
- Show in-app messaging to prompt payment method update.

### Account Hold

- Follows grace period if payment still fails.
- User **loses access** during account hold.
- Configured per base plan (up to 30 days).
- If payment recovers, subscription resumes. Otherwise it expires.

### Pause

- User-initiated pause (1–3 months).
- User **loses access** during pause.
- Subscription resumes automatically after pause duration.

### In-App Messaging for Payment Recovery

```kotlin
fun showBillingMessages(activity: Activity) {
    val params = InAppMessageParams.newBuilder()
        .addInAppMessageCategoryToShow(InAppMessageCategoryId.TRANSACTIONAL)
        .build()

    billingClient.showInAppMessages(activity, params) { result ->
        if (result.responseCode == InAppMessageResponseCode.SUBSCRIPTION_STATUS_UPDATED) {
            // Payment recovered — refresh entitlement from backend
            refreshSubscriptionStatus(result.purchaseToken)
        }
    }
}
```

Call `showInAppMessages` on `onResume` of your main activity to catch payment issues early.

### Deep Link to Subscription Management

```kotlin
// Link to a specific subscription in Play Store
fun getSubscriptionManagementUrl(productId: String, packageName: String): String =
    "https://play.google.com/store/account/subscriptions?sku=$productId&package=$packageName"

// Link to all subscriptions
val allSubscriptionsUrl = "https://play.google.com/store/account/subscriptions"
```


## Alternative Billing

Google Play supports alternative billing systems in certain markets. This is optional — most apps only need standard Google Play Billing.

### User Choice Billing

Users choose between Google Play's billing and a third-party payment provider at checkout. Available in select markets (EEA, US, others). Google reduces its service fee by 4% when the user selects the alternative.

**Requirements:**
- PBL 5.2+ for user choice billing APIs.
- Enrollment in the User Choice Billing program via Play Console.
- Separate reporting for alternative billing transactions.

### When to Consider

- Apps with existing payment infrastructure (web, iOS) that want a consistent cross-platform experience.
- Markets where alternative billing is mandated (EEA Digital Markets Act compliance).
- High-volume apps where the 4% fee reduction is material.

> For implementation details, see the [official guide](https://developer.android.com/google/play/billing/alternative/alternative-billing-with-user-choice-in-app).


## Testing

### License Testers

Set up in Play Console → **Settings → License testing**. License testers:
- Use test payment instruments (no real charges).
- Get accelerated subscription renewals.
- Can sideload debug builds (package name must match Play Store app).

### Test Payment Instruments

| Instrument | Behavior |
|------------|----------|
| Test card, always approves | Successful purchase |
| Test card, always declines | Payment failure |
| Slow test card, approves after a few minutes | Delayed success (test pending purchases) |
| Slow test card, declines after a few minutes | Delayed failure (test pending decline) |

### Accelerated Subscription Renewals (License Testers)

| Production Period | Test Renewal | Max Renewals |
|-------------------|-------------|--------------|
| 1 week | 5 min | 6 |
| 1 month | 5 min | 6 |
| 3 months | 10 min | 6 |
| 6 months | 15 min | 6 |
| 1 year | 30 min | 6 |

| Feature | Test Duration |
|---------|--------------|
| Free trial | 3 min |
| Grace period | 5 min |
| Account hold | 10 min |
| Pause (1 month) | 5 min |

### Play Billing Lab

Install [Play Billing Lab](https://play.google.com/store/apps/details?id=com.google.android.apps.play.billingtestcompanion) on the test device for advanced testing:

- **Change Play country** — test regional pricing (expires in 2 hours).
- **Reset trial eligibility** — unlimited trial testing with the same account.
- **Accelerate subscription states** — manually transition through grace period, account hold, etc.
- **Test price changes** — modify prices without affecting other subscribers.

### Testing Checklist

- [ ] Successful purchase (one-time and subscription)
- [ ] User cancellation mid-flow
- [ ] Payment decline
- [ ] Pending purchase → approved
- [ ] Pending purchase → declined
- [ ] Purchase acknowledgement (verify 3-day refund does NOT happen)
- [ ] Consumable re-purchase after consumption
- [ ] Subscription upgrade / downgrade (each replacement mode used in the app)
- [ ] Subscription renewal (wait for accelerated renewal)
- [ ] Grace period recovery
- [ ] Account hold → payment fix → resume
- [ ] Subscription pause and resume
- [ ] Subscription cancellation and expiry
- [ ] App killed during purchase flow → restore on relaunch
- [ ] Multi-device purchase restoration
- [ ] Promo code redemption


## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Not acknowledging purchases | Acknowledge within 3 days or Google auto-refunds. Set up monitoring for unacknowledged tokens. |
| Granting access for PENDING purchases | Only grant when `purchaseState == PURCHASED`. Show a "payment processing" state for PENDING. |
| Caching `ProductDetails` across sessions | Re-query each time the purchase UI is shown. Stale offer tokens cause `launchBillingFlow` to fail. |
| Ignoring `linkedPurchaseToken` on upgrades | Invalidate the old token on your backend to prevent duplicate entitlements. |
| Not calling `queryPurchasesAsync` on launch | Purchases can happen outside the app (promo codes, Play Store). Always restore on launch. |
| Testing only with license testers | Also test with real accounts on a closed test track before release. License tester behavior differs (accelerated renewals, no real charges). |
| Not handling `onBillingServiceDisconnected` | Use `enableAutoServiceReconnection()` (PBL 8+) or implement retry with exponential backoff. |
| Verifying purchases only on client | Always verify purchase tokens on your secure backend via Google Play Developer API. |
| Forgetting `enablePendingPurchases()` | Required since PBL 5 — `BillingClient.newBuilder` will throw if omitted. |
| Not enabling RTDN | Without Real-Time Developer Notifications, your backend misses out-of-band state changes (refunds, renewals, holds). |
