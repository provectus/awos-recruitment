# SwiftUI Patterns Reference

Deep-dive companion to the main `SKILL.md`. Covers view composition, property wrappers, navigation, state management, lists, forms, custom modifiers, animations, presentation, environment/DI, SwiftData integration, and performance. Targets Swift 6+ and iOS 17+ unless noted otherwise.


## View Composition

### Extracting Subviews
---

Keep `body` under ~30 lines. Extract meaningful subviews as `private` computed properties or dedicated types.

```swift
struct OrderDetailView: View {
    let order: Order

    var body: some View {
        ScrollView {
            headerSection
            itemsList
            totalSection
        }
    }

    // MARK: - Subviews

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(order.title)
                .font(.title2.bold())
            Text(order.date, style: .date)
                .foregroundStyle(.secondary)
        }
        .padding()
    }

    private var itemsList: some View {
        ForEach(order.items) { item in
            OrderItemRow(item: item)
        }
    }

    private var totalSection: some View {
        HStack {
            Text("Total")
                .font(.headline)
            Spacer()
            Text(order.total, format: .currency(code: "USD"))
                .font(.headline)
        }
        .padding()
    }
}
```

When a subview needs its own state or bindings, extract it into a separate `struct`.

### ViewBuilder
---

Use `@ViewBuilder` to create functions or properties that return opaque view types, and to build custom container views.

```swift
struct Card<Content: View>: View {
    let title: String
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.headline)
            content()
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

// Usage
Card(title: "Statistics") {
    Text("Downloads: 1,204")
    Text("Revenue: $3,400")
}
```

### Custom Containers
---

For more complex containers, accept content via `init` with a `@ViewBuilder` closure. Use generics to keep the container agnostic to content type.

```swift
struct SectionContainer<Header: View, Content: View>: View {
    let header: Header
    let content: Content

    init(
        @ViewBuilder header: () -> Header,
        @ViewBuilder content: () -> Content
    ) {
        self.header = header()
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            header
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.secondary)
            content
        }
    }
}
```

### Generic Helper Views
---

```swift
/// Renders content based on a loading state enum.
struct AsyncContentView<T, Loading: View, Loaded: View, Failed: View>: View {
    let state: LoadingState<T>
    @ViewBuilder let loading: () -> Loading
    @ViewBuilder let loaded: (T) -> Loaded
    @ViewBuilder let failed: (Error) -> Failed

    var body: some View {
        switch state {
        case .idle:
            Color.clear
        case .loading:
            loading()
        case .loaded(let value):
            loaded(value)
        case .failed(let error):
            failed(error)
        }
    }
}
```

### Custom Container APIs (iOS 18+)
---

iOS 18 introduced `ForEach(subviewOf:)` and `Group(subviews:)` for building custom container views that can introspect and rearrange their children — something previously impossible without workarounds.

```swift
struct TwoColumn: View {
    @ViewBuilder var content: some View

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Group(subviews: content) { subviews in
                // Access subviews as a RandomAccessCollection
                VStack { ForEach(subviews.prefix(2)) { $0 } }
                VStack { ForEach(subviews.dropFirst(2)) { $0 } }
            }
        }
    }
}
```

These APIs let containers inspect child count, apply per-child styling, and implement layouts like multi-column or card stacks declaratively.


## Property Wrappers

### Quick Reference Table
---

| Wrapper | Scope | Use Case | Min iOS |
|---|---|---|---|
| `@State` | View-local value | Simple view state (toggles, text, counts) | 13 |
| `@Binding` | Parent-child | Pass writable reference to child view | 13 |
| `@Observable` | Model object | Observable reference type (replaces `ObservableObject`) | 17 |
| `@Bindable` | Binding from `@Observable` | Create bindings to `@Observable` properties | 17 |
| `@Environment` | View hierarchy | Read values from the environment | 13 |
| `@AppStorage` | `UserDefaults` | Persist small values across launches | 14 |
| `@SceneStorage` | Scene state | Persist per-scene state for restoration | 14 |
| `@FocusState` | Focus control | Manage keyboard focus | 15 |
| `@Query` | SwiftData | Fetch model objects declaratively | 17 |

### @State
---

Owns simple, view-local state. SwiftUI manages storage; the view re-renders when the value changes.

```swift
struct CounterView: View {
    @State private var count = 0

    var body: some View {
        Button("Count: \(count)") {
            count += 1
        }
    }
}
```

With iOS 17+, `@State` can also hold `@Observable` objects when the view owns the model's lifetime:

```swift
struct ProfileView: View {
    @State private var viewModel = ProfileViewModel()

    var body: some View {
        Text(viewModel.displayName)
            .task { await viewModel.load() }
    }
}
```

**Caveat:** Unlike `@StateObject`, `@State` re-evaluates the initializer expression on every view struct recreation (SwiftUI discards the new instance, but `init()` still runs). Avoid side effects in `@Observable` class initializers — use `.task` for deferred setup.

### @Binding
---

Provides read-write access to state owned by a parent. Does not own storage.

```swift
struct ToggleRow: View {
    let title: String
    @Binding var isOn: Bool

    var body: some View {
        Toggle(title, isOn: $isOn)
    }
}

// Parent
struct SettingsView: View {
    @State private var notificationsEnabled = true

    var body: some View {
        ToggleRow(title: "Notifications", isOn: $notificationsEnabled)
    }
}
```

### @Observable (iOS 17+)
---

Macro that makes a class observable without `ObservableObject` or `@Published`. SwiftUI tracks property access at the per-property level, reducing unnecessary redraws.

```swift
@Observable
class ShoppingCart {
    var items: [CartItem] = []
    var couponCode: String?

    var total: Decimal {
        items.reduce(0) { $0 + $1.price * Decimal($1.quantity) }
    }

    func add(_ product: Product) {
        items.append(CartItem(product: product, quantity: 1))
    }
}
```

Use `@Bindable` to create bindings to properties of an `@Observable` object:

```swift
struct CouponEntryView: View {
    @Bindable var cart: ShoppingCart

    var body: some View {
        TextField("Coupon code", text: Binding(
            get: { cart.couponCode ?? "" },
            set: { cart.couponCode = $0.isEmpty ? nil : $0 }
        ))
    }
}
```

### @Environment
---

Reads values from the SwiftUI environment. Used for system-provided values and custom dependencies.

```swift
struct DetailView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.horizontalSizeClass) private var sizeClass

    var body: some View {
        VStack {
            Text("Detail")
            Button("Close") { dismiss() }
        }
    }
}
```

With iOS 17+, `@Environment` also works with `@Observable` types directly (see Environment and Dependency Injection section below).

### @AppStorage
---

Reads and writes to `UserDefaults`. Suitable for small preferences; not for large data.

```swift
struct AppearanceSettings: View {
    @AppStorage("selectedTheme") private var theme: String = "system"
    @AppStorage("fontSize") private var fontSize: Double = 14.0

    var body: some View {
        Form {
            Picker("Theme", selection: $theme) {
                Text("System").tag("system")
                Text("Light").tag("light")
                Text("Dark").tag("dark")
            }
            Slider(value: $fontSize, in: 10...24, step: 1) {
                Text("Font Size: \(Int(fontSize))")
            }
        }
    }
}
```

### @SceneStorage
---

Persists lightweight per-scene state for scene restoration (e.g., scroll position, selected tab). Data is not shared across scenes or app launches in all cases.

```swift
struct ContentView: View {
    @SceneStorage("selectedTab") private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            HomeView().tag(0).tabItem { Label("Home", systemImage: "house") }
            SearchView().tag(1).tabItem { Label("Search", systemImage: "magnifyingglass") }
        }
    }
}
```

### @FocusState
---

Manages keyboard focus across text fields. See Forms and Input section for detailed patterns.

```swift
struct LoginForm: View {
    enum Field { case email, password }

    @State private var email = ""
    @State private var password = ""
    @FocusState private var focusedField: Field?

    var body: some View {
        Form {
            TextField("Email", text: $email)
                .focused($focusedField, equals: .email)
                .submitLabel(.next)
                .onSubmit { focusedField = .password }

            SecureField("Password", text: $password)
                .focused($focusedField, equals: .password)
                .submitLabel(.go)
                .onSubmit { login() }
        }
        .onAppear { focusedField = .email }
    }

    private func login() { /* ... */ }
}
```

### @Query (SwiftData)
---

Declaratively fetches SwiftData models. See SwiftData Integration section below.

### Legacy Wrappers (Pre-iOS 17)
---

These wrappers are still valid for codebases targeting iOS 16 and earlier. Avoid them in new iOS 17+ code.

| Wrapper | Modern Replacement | Notes |
|---|---|---|
| `@StateObject` | `@State` + `@Observable` | Owned ObservableObject in a view |
| `@ObservedObject` | Direct reference to `@Observable` | Non-owned ObservableObject |
| `@EnvironmentObject` | `@Environment` + `@Observable` | Injected ObservableObject |

```swift
// Legacy pattern (pre-iOS 17) — do NOT use in new code
class LegacyViewModel: ObservableObject {
    @Published var items: [Item] = []
}

struct LegacyView: View {
    @StateObject private var viewModel = LegacyViewModel()  // owns it
    var body: some View {
        ChildView(viewModel: viewModel)
    }
}

struct ChildView: View {
    @ObservedObject var viewModel: LegacyViewModel          // borrows it
    var body: some View { Text("\(viewModel.items.count)") }
}
```


## Navigation

`NavigationView` is deprecated as of iOS 16. Use `NavigationStack` or `NavigationSplitView`.

### NavigationStack
---

Stack-based navigation with value-driven destinations. Supports programmatic navigation and deep linking.

```swift
struct AppNavigationView: View {
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            List(Category.allCases) { category in
                NavigationLink(value: category) {
                    Label(category.title, systemImage: category.icon)
                }
            }
            .navigationTitle("Browse")
            .navigationDestination(for: Category.self) { category in
                CategoryDetailView(category: category, path: $path)
            }
            .navigationDestination(for: Product.self) { product in
                ProductDetailView(product: product)
            }
        }
    }
}
```

### Typed Destinations
---

Use `Hashable` types as navigation values for type-safe, composable routing.

```swift
enum Route: Hashable {
    case profile(User.ID)
    case settings
    case orderDetail(Order.ID)
}

struct RootView: View {
    @State private var path: [Route] = []

    var body: some View {
        NavigationStack(path: $path) {
            HomeView(path: $path)
                .navigationDestination(for: Route.self) { route in
                    switch route {
                    case .profile(let userID):
                        ProfileView(userID: userID)
                    case .settings:
                        SettingsView()
                    case .orderDetail(let orderID):
                        OrderDetailView(orderID: orderID)
                    }
                }
        }
    }
}
```

### Programmatic Navigation
---

Push, pop, and reset the stack by mutating the path.

```swift
struct HomeView: View {
    @Binding var path: [Route]

    var body: some View {
        VStack {
            Button("Go to Settings") {
                path.append(.settings)
            }
            Button("Go to Profile") {
                path.append(.profile(currentUserID))
            }
            Button("Pop to Root") {
                path.removeAll()
            }
        }
    }
}
```

### NavigationSplitView
---

Two- or three-column navigation for iPadOS and macOS.

```swift
struct MailView: View {
    @State private var selectedMailbox: Mailbox?
    @State private var selectedMessage: Message?

    var body: some View {
        NavigationSplitView {
            // Sidebar
            List(mailboxes, selection: $selectedMailbox) { mailbox in
                Label(mailbox.name, systemImage: mailbox.icon)
            }
            .navigationTitle("Mailboxes")
        } content: {
            // Content column
            if let mailbox = selectedMailbox {
                List(mailbox.messages, selection: $selectedMessage) { message in
                    MessageRow(message: message)
                }
            } else {
                ContentUnavailableView("Select a Mailbox", systemImage: "tray")
            }
        } detail: {
            // Detail column
            if let message = selectedMessage {
                MessageDetailView(message: message)
            } else {
                ContentUnavailableView("Select a Message", systemImage: "envelope")
            }
        }
    }
}
```

### Deep Linking
---

Combine `NavigationPath` with URL/activity parsing to restore navigation state.

```swift
@Observable
class NavigationState {
    var path = NavigationPath()

    func handleDeepLink(_ url: URL) {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return }

        // Reset to root, then push the target
        path = NavigationPath()

        switch components.path {
        case "/order":
            if let id = components.queryItems?.first(where: { $0.name == "id" })?.value {
                path.append(Route.orderDetail(id))
            }
        case "/settings":
            path.append(Route.settings)
        default:
            break
        }
    }
}
```


## State Management

### @Observable Macro (iOS 17+)
---

The `@Observable` macro generates observation tracking at the per-property level. SwiftUI views only re-render when a property they actually read changes, unlike `ObservableObject` which triggers on any `@Published` change.

```swift
@Observable
class UserSession {
    var currentUser: User?
    var isAuthenticated: Bool { currentUser != nil }
    var preferences = UserPreferences()

    // Properties not read by a view won't cause re-renders
    var analyticsBuffer: [Event] = []

    func signIn(email: String, password: String) async throws {
        currentUser = try await authService.signIn(email: email, password: password)
    }

    func signOut() {
        currentUser = nil
    }
}
```

### Observation Tracking
---

The `@Observable` macro instruments property getters. SwiftUI's `withObservationTracking` records which properties are read during `body` evaluation, then invalidates only when those specific properties change.

Key differences from `ObservableObject`:

| `ObservableObject` (legacy) | `@Observable` (iOS 17+) |
|---|---|
| View re-renders on any `@Published` change | View re-renders only when accessed properties change |
| Requires `@Published` on each property | All stored properties tracked automatically |
| Uses Combine under the hood | Uses Swift observation framework |
| `@StateObject` / `@ObservedObject` in views | `@State` for owned, direct reference for non-owned |

### @Bindable
---

Creates bindings to properties on an `@Observable` object. Required when you need `$` binding syntax.

```swift
@Observable
class EditorModel {
    var title = ""
    var body = ""
    var isDraft = true
}

struct EditorView: View {
    @Bindable var model: EditorModel

    var body: some View {
        Form {
            TextField("Title", text: $model.title)
            TextEditor(text: $model.body)
            Toggle("Draft", isOn: $model.isDraft)
        }
    }
}

// Parent view that owns the model
struct DocumentView: View {
    @State private var editor = EditorModel()

    var body: some View {
        EditorView(model: editor) // @State provides @Bindable automatically
    }
}
```

### Sharing Observable State
---

Pass `@Observable` objects through the environment for app-wide state:

```swift
@main
struct MyApp: App {
    @State private var session = UserSession()
    @State private var settings = AppSettings()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(session)
                .environment(settings)
        }
    }
}

struct ProfileView: View {
    @Environment(UserSession.self) private var session

    var body: some View {
        if let user = session.currentUser {
            Text("Hello, \(user.name)")
        }
    }
}
```


## Lists and Grids

### List
---

Use `List` for standard scrollable lists with built-in styling, swipe actions, and selection.

```swift
struct TaskListView: View {
    @State private var tasks: [TaskItem] = TaskItem.samples
    @State private var selection: Set<TaskItem.ID> = []

    var body: some View {
        List(selection: $selection) {
            ForEach($tasks) { $task in
                TaskRow(task: $task)
                    .swipeActions(edge: .trailing) {
                        Button(role: .destructive) {
                            tasks.removeAll { $0.id == task.id }
                        } label: {
                            Label("Delete", systemImage: "trash")
                        }
                    }
                    .swipeActions(edge: .leading) {
                        Button {
                            task.isCompleted.toggle()
                        } label: {
                            Label(
                                task.isCompleted ? "Undo" : "Done",
                                systemImage: task.isCompleted ? "arrow.uturn.left" : "checkmark"
                            )
                        }
                        .tint(task.isCompleted ? .orange : .green)
                    }
            }
            .onMove { tasks.move(fromOffsets: $0, toOffset: $1) }
        }
        .listStyle(.insetGrouped)
        .toolbar { EditButton() }
    }
}
```

### Sections in Lists
---

```swift
List {
    Section("Pinned") {
        ForEach(pinnedItems) { item in
            ItemRow(item: item)
        }
    }

    Section("Recent") {
        ForEach(recentItems) { item in
            ItemRow(item: item)
        }
    }
}
```

### LazyVStack with ScrollView
---

Use `LazyVStack` inside a `ScrollView` when you need more layout control than `List` provides, or when working with large datasets.

```swift
struct FeedView: View {
    let posts: [Post]

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 16) {
                ForEach(posts) { post in
                    PostCard(post: post)
                        .padding(.horizontal)
                }
            }
            .padding(.vertical)
        }
    }
}
```

### LazyVGrid / LazyHGrid
---

Grid layouts with flexible, fixed, or adaptive columns.

```swift
struct PhotoGridView: View {
    let photos: [Photo]

    private let columns = [
        GridItem(.adaptive(minimum: 100, maximum: 200), spacing: 4)
    ]

    var body: some View {
        ScrollView {
            LazyVGrid(columns: columns, spacing: 4) {
                ForEach(photos) { photo in
                    AsyncImage(url: photo.thumbnailURL) { image in
                        image
                            .resizable()
                            .scaledToFill()
                    } placeholder: {
                        Color.gray.opacity(0.3)
                    }
                    .frame(minHeight: 100)
                    .clipShape(RoundedRectangle(cornerRadius: 4))
                }
            }
            .padding(4)
        }
    }
}
```

Fixed-column grid:

```swift
private let columns = [
    GridItem(.flexible()),
    GridItem(.flexible()),
    GridItem(.flexible())
]
```

### Performance with Large Data Sets
---

- Prefer `LazyVStack` / `LazyVGrid` over `VStack` / `VGrid` for collections larger than ~50 items.
- Ensure `ForEach` items conform to `Identifiable` with stable IDs. Avoid using array indices as IDs.
- Use `.id()` with stable identifiers so SwiftUI can diff efficiently.
- For paginated loading, trigger fetches near the end of the list:

```swift
struct PaginatedListView: View {
    @State private var viewModel = PaginatedViewModel()

    var body: some View {
        List(viewModel.items) { item in
            ItemRow(item: item)
                .onAppear {
                    if item.id == viewModel.items.last?.id {
                        Task { await viewModel.loadNextPage() }
                    }
                }
        }
        .task { await viewModel.loadNextPage() }
    }
}
```

### ScrollView Patterns
---

```swift
ScrollView {
    LazyVStack {
        ForEach(items) { item in
            ItemRow(item: item)
        }
    }
}
.scrollIndicators(.hidden)
.scrollDismissesKeyboard(.interactively)  // iOS 16+
.contentMargins(16)                       // iOS 17+
```

Scroll position tracking (iOS 17+):

```swift
struct ScrollableList: View {
    @State private var scrollPosition: Item.ID?

    var body: some View {
        ScrollView {
            LazyVStack {
                ForEach(items) { item in
                    ItemRow(item: item)
                }
            }
            .scrollTargetLayout()
        }
        .scrollPosition(id: $scrollPosition)

        // Programmatic scroll
        Button("Scroll to Top") {
            withAnimation {
                scrollPosition = items.first?.id
            }
        }
    }
}
```


## Forms and Input

### Form Basics
---

`Form` provides platform-appropriate styling for settings and data entry screens.

```swift
struct ProfileEditView: View {
    @State private var name = ""
    @State private var bio = ""
    @State private var isPublic = true
    @State private var notificationFrequency = NotificationFrequency.daily

    var body: some View {
        Form {
            Section("Personal Info") {
                TextField("Name", text: $name)
                TextField("Bio", text: $bio, axis: .vertical)
                    .lineLimit(3...6)
            }

            Section("Privacy") {
                Toggle("Public Profile", isOn: $isPublic)
                Picker("Notifications", selection: $notificationFrequency) {
                    ForEach(NotificationFrequency.allCases) { freq in
                        Text(freq.label).tag(freq)
                    }
                }
            }

            Section {
                Button("Save", action: save)
                    .disabled(!isFormValid)
            }
        }
    }

    private var isFormValid: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private func save() { /* ... */ }
}
```

### Validation Patterns
---

Combine computed properties for validation state with visual feedback:

```swift
struct RegistrationView: View {
    @State private var email = ""
    @State private var password = ""
    @State private var hasAttemptedSubmit = false

    private var emailError: String? {
        guard hasAttemptedSubmit else { return nil }
        if email.isEmpty { return "Email is required" }
        if !email.contains("@") { return "Enter a valid email" }
        return nil
    }

    private var passwordError: String? {
        guard hasAttemptedSubmit else { return nil }
        if password.count < 8 { return "At least 8 characters required" }
        return nil
    }

    var body: some View {
        Form {
            Section {
                TextField("Email", text: $email)
                    .textContentType(.emailAddress)
                    .keyboardType(.emailAddress)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                if let error = emailError {
                    Text(error).foregroundStyle(.red).font(.caption)
                }

                SecureField("Password", text: $password)
                    .textContentType(.newPassword)
                if let error = passwordError {
                    Text(error).foregroundStyle(.red).font(.caption)
                }
            }

            Button("Register") {
                hasAttemptedSubmit = true
                guard emailError == nil, passwordError == nil else { return }
                register()
            }
        }
    }

    private func register() { /* ... */ }
}
```

### @FocusState for Keyboard Management
---

Control focus programmatically for multi-field forms:

```swift
struct AddressForm: View {
    enum Field: CaseIterable {
        case street, city, state, zip
    }

    @State private var street = ""
    @State private var city = ""
    @State private var state = ""
    @State private var zip = ""
    @FocusState private var focusedField: Field?

    var body: some View {
        Form {
            TextField("Street", text: $street)
                .focused($focusedField, equals: .street)
                .submitLabel(.next)
                .onSubmit { focusedField = .city }

            TextField("City", text: $city)
                .focused($focusedField, equals: .city)
                .submitLabel(.next)
                .onSubmit { focusedField = .state }

            TextField("State", text: $state)
                .focused($focusedField, equals: .state)
                .submitLabel(.next)
                .onSubmit { focusedField = .zip }

            TextField("ZIP", text: $zip)
                .focused($focusedField, equals: .zip)
                .keyboardType(.numberPad)
                .submitLabel(.done)
                .onSubmit { focusedField = nil }
        }
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Button("Previous") { moveFocus(forward: false) }
                Button("Next") { moveFocus(forward: true) }
                Spacer()
                Button("Done") { focusedField = nil }
            }
        }
    }

    private func moveFocus(forward: Bool) {
        guard let current = focusedField,
              let index = Field.allCases.firstIndex(of: current) else { return }
        let nextIndex = forward
            ? Field.allCases.index(after: index)
            : Field.allCases.index(before: index)
        guard Field.allCases.indices.contains(nextIndex) else { return }
        focusedField = Field.allCases[nextIndex]
    }
}
```


## Custom View Modifiers

### ViewModifier Protocol
---

Encapsulate reusable styling or behavior in a `ViewModifier` and expose it via a `View` extension.

```swift
struct CardStyle: ViewModifier {
    var cornerRadius: CGFloat = 12

    func body(content: Content) -> some View {
        content
            .padding()
            .background(.background, in: RoundedRectangle(cornerRadius: cornerRadius))
            .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
    }
}

extension View {
    func cardStyle(cornerRadius: CGFloat = 12) -> some View {
        modifier(CardStyle(cornerRadius: cornerRadius))
    }
}

// Usage
Text("Hello")
    .cardStyle()
```

### Conditional Modifiers
---

Avoid `if/else` in modifier chains (it changes view identity). Use a dedicated modifier or `opacity`/`disabled` instead.

```swift
// Preferred: dedicated modifier that always applies
extension View {
    @ViewBuilder
    func shimmer(isActive: Bool) -> some View {
        if isActive {
            self.redacted(reason: .placeholder)
                .shimmering() // hypothetical shimmer modifier
        } else {
            self
        }
    }
}

// Avoid this pattern — it destroys view identity and breaks animations:
// someView
//     .if(condition) { view in view.opacity(0.5) }
```

If you truly need conditional application, wrap it with `@ViewBuilder` in a dedicated function as shown above, and understand the identity implications.

### Preference Keys
---

Use `PreferenceKey` to pass data up the view hierarchy (child to parent).

```swift
struct SizePreferenceKey: PreferenceKey {
    static var defaultValue: CGSize = .zero
    static func reduce(value: inout CGSize, nextValue: () -> CGSize) {
        value = nextValue()
    }
}

extension View {
    func readSize(onChange: @escaping (CGSize) -> Void) -> some View {
        background(
            GeometryReader { geometry in
                Color.clear
                    .preference(key: SizePreferenceKey.self, value: geometry.size)
            }
        )
        .onPreferenceChange(SizePreferenceKey.self, perform: onChange)
    }
}

// Usage
struct DynamicHeader: View {
    @State private var headerHeight: CGFloat = 0

    var body: some View {
        VStack {
            headerContent
                .readSize { headerHeight = $0.height }

            // Use headerHeight for layout calculations
            ScrollView { /* ... */ }
                .padding(.top, headerHeight)
        }
    }
}
```

> **iOS 18+:** For many geometry-reading use cases, `onGeometryChange(for:of:action:)` (back-deployed to iOS 16) is a simpler alternative that avoids the `PreferenceKey` boilerplate entirely:
>
> ```swift
> headerContent
>     .onGeometryChange(for: CGFloat.self) { proxy in
>         proxy.size.height
>     } action: { height in
>         headerHeight = height
>     }
> ```


## Animations

### withAnimation
---

Wrap state changes in `withAnimation` to animate all resulting view updates.

```swift
struct ExpandableCard: View {
    @State private var isExpanded = false

    var body: some View {
        VStack {
            Button("Toggle") {
                withAnimation(.spring(duration: 0.4, bounce: 0.2)) {
                    isExpanded.toggle()
                }
            }

            if isExpanded {
                Text("Expanded content here")
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
    }
}
```

### .animation() Modifier
---

Applies animation to a view whenever a specific value changes. Prefer explicit `withAnimation` for clarity; use `.animation(_:value:)` for local, continuous changes.

```swift
struct ProgressBar: View {
    var progress: Double

    var body: some View {
        GeometryReader { geometry in
            RoundedRectangle(cornerRadius: 4)
                .fill(.blue)
                .frame(width: geometry.size.width * progress)
                .animation(.easeInOut(duration: 0.3), value: progress)
        }
        .frame(height: 8)
        .background(.gray.opacity(0.2), in: RoundedRectangle(cornerRadius: 4))
    }
}
```

### Matched Geometry Effect
---

Animates a shared element between two views using `@Namespace`.

```swift
struct HeroAnimationView: View {
    @Namespace private var animation
    @State private var isExpanded = false
    let item: GalleryItem

    var body: some View {
        if isExpanded {
            // Expanded state
            VStack {
                Image(item.imageName)
                    .resizable()
                    .scaledToFit()
                    .matchedGeometryEffect(id: item.id, in: animation)
                    .onTapGesture {
                        withAnimation(.spring(duration: 0.5)) { isExpanded = false }
                    }
                Text(item.title)
                    .font(.title)
            }
        } else {
            // Thumbnail state
            Image(item.imageName)
                .resizable()
                .scaledToFill()
                .frame(width: 80, height: 80)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .matchedGeometryEffect(id: item.id, in: animation)
                .onTapGesture {
                    withAnimation(.spring(duration: 0.5)) { isExpanded = true }
                }
        }
    }
}
```

### Transitions
---

Control how views appear and disappear.

```swift
struct NotificationBanner: View {
    @State private var isVisible = false

    var body: some View {
        VStack {
            if isVisible {
                Text("Operation completed")
                    .padding()
                    .background(.green, in: RoundedRectangle(cornerRadius: 8))
                    .transition(
                        .asymmetric(
                            insertion: .move(edge: .top).combined(with: .opacity),
                            removal: .move(edge: .top).combined(with: .opacity)
                        )
                    )
            }
            Spacer()
        }
    }
}
```

### Phase Animator (iOS 17+)
---

Cycles through a sequence of phases, applying changes at each step.

```swift
struct PulsingDot: View {
    @State private var isAnimating = false

    var body: some View {
        Circle()
            .fill(.blue)
            .frame(width: 20, height: 20)
            .phaseAnimator([false, true]) { content, phase in
                content
                    .scaleEffect(phase ? 1.2 : 1.0)
                    .opacity(phase ? 0.6 : 1.0)
            } animation: { phase in
                    .easeInOut(duration: 0.8)
            }
    }
}
```

Custom phase sequences:

```swift
enum BouncePhase: CaseIterable {
    case initial, up, down

    var yOffset: Double {
        switch self {
        case .initial: 0
        case .up: -30
        case .down: 0
        }
    }

    var scale: Double {
        switch self {
        case .initial: 1.0
        case .up: 1.1
        case .down: 0.95
        }
    }
}

struct BouncingIcon: View {
    var body: some View {
        Image(systemName: "bell.fill")
            .font(.largeTitle)
            .phaseAnimator(BouncePhase.allCases) { content, phase in
                content
                    .offset(y: phase.yOffset)
                    .scaleEffect(phase.scale)
            } animation: { _ in
                .spring(duration: 0.4, bounce: 0.5)
            }
    }
}
```

### Keyframe Animator (iOS 17+)
---

For multi-property animations with independent timing:

```swift
struct WiggleEffect: View {
    @State private var trigger = false

    var body: some View {
        Image(systemName: "bell.fill")
            .font(.largeTitle)
            .keyframeAnimator(initialValue: AnimationValues(), trigger: trigger) { content, value in
                content
                    .rotationEffect(value.rotation)
                    .scaleEffect(value.scale)
            } keyframes: { _ in
                KeyframeTrack(\.rotation) {
                    SpringKeyframe(.degrees(-15), duration: 0.15)
                    SpringKeyframe(.degrees(15), duration: 0.15)
                    SpringKeyframe(.degrees(-10), duration: 0.15)
                    SpringKeyframe(.degrees(0), duration: 0.15)
                }
                KeyframeTrack(\.scale) {
                    SpringKeyframe(1.2, duration: 0.15)
                    SpringKeyframe(1.0, duration: 0.45)
                }
            }
            .onTapGesture { trigger.toggle() }
    }
}

struct AnimationValues {
    var rotation: Angle = .zero
    var scale: Double = 1.0
}
```


## Sheets, Alerts, Confirmations

### Sheet Presentation
---

Use `.sheet(item:)` over `.sheet(isPresented:)` when the presented content depends on data.

```swift
struct ItemListView: View {
    @State private var selectedItem: Item?
    @State private var showingNewItemSheet = false

    var body: some View {
        List(items) { item in
            Button(item.title) {
                selectedItem = item
            }
        }
        // Item-based presentation — the sheet receives the selected item
        .sheet(item: $selectedItem) { item in
            ItemDetailView(item: item)
        }
        // Boolean-based presentation — for sheets that don't depend on data
        .sheet(isPresented: $showingNewItemSheet) {
            NewItemView()
        }
        .toolbar {
            Button("Add", systemImage: "plus") {
                showingNewItemSheet = true
            }
        }
    }
}
```

### Full-Screen Cover
---

```swift
.fullScreenCover(item: $selectedPhoto) { photo in
    PhotoViewer(photo: photo)
}
```

### Dismissing Presented Views
---

```swift
struct NewItemView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""

    var body: some View {
        NavigationStack {
            Form {
                TextField("Title", text: $title)
            }
            .navigationTitle("New Item")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        save()
                        dismiss()
                    }
                    .disabled(title.isEmpty)
                }
            }
        }
    }

    private func save() { /* ... */ }
}
```

### Alerts
---

```swift
struct DangerZoneView: View {
    @State private var showingDeleteAlert = false
    @State private var error: AppError?

    var body: some View {
        Button("Delete Account", role: .destructive) {
            showingDeleteAlert = true
        }
        // Simple alert
        .alert("Delete Account?", isPresented: $showingDeleteAlert) {
            Button("Delete", role: .destructive) { deleteAccount() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This action cannot be undone.")
        }
        // Error alert driven by optional error
        .alert(
            "Error",
            isPresented: Binding(
                get: { error != nil },
                set: { if !$0 { error = nil } }
            ),
            presenting: error
        ) { _ in
            Button("OK") { error = nil }
        } message: { error in
            Text(error.localizedDescription)
        }
    }

    private func deleteAccount() { /* ... */ }
}
```

### Confirmation Dialog
---

```swift
struct PhotoActionView: View {
    @State private var showingOptions = false

    var body: some View {
        Button("Change Photo") {
            showingOptions = true
        }
        .confirmationDialog("Choose Source", isPresented: $showingOptions) {
            Button("Camera") { openCamera() }
            Button("Photo Library") { openLibrary() }
            Button("Remove Photo", role: .destructive) { removePhoto() }
        } message: {
            Text("Select a source for your profile photo.")
        }
    }
}
```


## Environment and Dependency Injection

### Custom EnvironmentKey
---

Define a custom key to inject dependencies through the SwiftUI view hierarchy.

> **iOS 18 / Xcode 16+:** The `@Entry` macro eliminates the boilerplate below and is back-deployed to iOS 13:
>
> ```swift
> extension EnvironmentValues {
>     @Entry var apiClient: APIClient = LiveAPIClient()
> }
> // Use: .environment(\.apiClient, MockAPIClient())
> // Read: @Environment(\.apiClient) private var apiClient
> ```
>
> The classic `EnvironmentKey` pattern shown below remains valid but is more verbose.

```swift
// 1. Define the key
struct APIClientKey: EnvironmentKey {
    static let defaultValue: APIClient = LiveAPIClient()
}

// 2. Extend EnvironmentValues
extension EnvironmentValues {
    var apiClient: APIClient {
        get { self[APIClientKey.self] }
        set { self[APIClientKey.self] = newValue }
    }
}

// 3. Inject at the root
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(\.apiClient, LiveAPIClient())
        }
    }
}

// 4. Consume in any descendant view
struct UserListView: View {
    @Environment(\.apiClient) private var apiClient
    @State private var users: [User] = []

    var body: some View {
        List(users) { user in
            Text(user.name)
        }
        .task {
            users = (try? await apiClient.fetchUsers()) ?? []
        }
    }
}
```

### @Observable in the Environment (iOS 17+)
---

With iOS 17+, you can place `@Observable` objects directly in the environment without needing a custom `EnvironmentKey`.

```swift
@Observable
class AppTheme {
    var primaryColor: Color = .blue
    var cornerRadius: CGFloat = 12
    var useDarkMode: Bool = false
}

// Inject
ContentView()
    .environment(AppTheme())

// Consume
struct ThemedButton: View {
    @Environment(AppTheme.self) private var theme

    var body: some View {
        Button("Action") { /* ... */ }
            .tint(theme.primaryColor)
    }
}
```

### Dependency Container Pattern
---

For larger apps, group related dependencies:

```swift
@Observable
class Dependencies {
    let apiClient: APIClient
    let authService: AuthService
    let analytics: AnalyticsService

    init(
        apiClient: APIClient = LiveAPIClient(),
        authService: AuthService = LiveAuthService(),
        analytics: AnalyticsService = LiveAnalyticsService()
    ) {
        self.apiClient = apiClient
        self.authService = authService
        self.analytics = analytics
    }

    /// Factory for SwiftUI previews and tests
    static var preview: Dependencies {
        Dependencies(
            apiClient: MockAPIClient(),
            authService: MockAuthService(),
            analytics: NoOpAnalyticsService()
        )
    }
}

// Inject once at root
@main
struct MyApp: App {
    @State private var dependencies = Dependencies()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(dependencies)
        }
    }
}
```


## SwiftData Integration

SwiftData is Apple's persistence framework (iOS 17+), built on top of Core Data with a Swift-native API. This section covers the essentials for SwiftUI integration. For a complete SwiftData guide, see dedicated resources.

### @Model
---

Mark your model classes with `@Model` to make them persistable.

```swift
@Model
class Expense {
    var title: String
    var amount: Decimal
    var date: Date
    var category: ExpenseCategory?

    @Relationship(deleteRule: .cascade)
    var receipts: [Receipt] = []

    init(title: String, amount: Decimal, date: Date = .now) {
        self.title = title
        self.amount = amount
        self.date = date
    }
}

@Model
class Receipt {
    var imageData: Data
    var expense: Expense?

    init(imageData: Data) {
        self.imageData = imageData
    }
}
```

### ModelContainer Setup
---

```swift
@main
struct ExpenseApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .modelContainer(for: [Expense.self, Receipt.self])
    }
}
```

For custom configuration:

```swift
let container = try ModelContainer(
    for: Expense.self, Receipt.self,
    configurations: ModelConfiguration(
        isStoredInMemoryOnly: false,
        allowsSave: true
    )
)
```

### @Query
---

Declaratively fetch and filter SwiftData models. The view automatically updates when data changes.

```swift
struct ExpenseListView: View {
    @Query(
        filter: #Predicate<Expense> { $0.amount > 0 },
        sort: \Expense.date,
        order: .reverse
    )
    private var expenses: [Expense]

    @Environment(\.modelContext) private var modelContext

    var body: some View {
        List {
            ForEach(expenses) { expense in
                ExpenseRow(expense: expense)
            }
            .onDelete(perform: deleteExpenses)
        }
    }

    private func deleteExpenses(at offsets: IndexSet) {
        for index in offsets {
            modelContext.delete(expenses[index])
        }
    }
}
```

Dynamic queries with sorting and filtering:

```swift
struct FilterableExpenseList: View {
    @State private var sortOrder = SortDescriptor(\Expense.date, order: .reverse)
    @State private var searchText = ""

    var body: some View {
        ExpenseResults(searchText: searchText, sortOrder: sortOrder)
            .searchable(text: $searchText)
    }
}

struct ExpenseResults: View {
    @Query private var expenses: [Expense]

    init(searchText: String, sortOrder: SortDescriptor<Expense>) {
        let predicate: Predicate<Expense>? = searchText.isEmpty
            ? nil
            : #Predicate { $0.title.localizedStandardContains(searchText) }

        _expenses = Query(filter: predicate, sort: [sortOrder])
    }

    var body: some View {
        ForEach(expenses) { expense in
            ExpenseRow(expense: expense)
        }
    }
}
```

### ModelContext Operations
---

```swift
struct AddExpenseView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var amount: Decimal = 0

    var body: some View {
        Form {
            TextField("Title", text: $title)
            TextField("Amount", value: $amount, format: .currency(code: "USD"))
                .keyboardType(.decimalPad)

            Button("Save") {
                let expense = Expense(title: title, amount: amount)
                modelContext.insert(expense)
                dismiss()
            }
            .disabled(title.isEmpty)
        }
    }
}
```


## Performance

### Avoiding Unnecessary Redraws
---

SwiftUI re-evaluates `body` when observed state changes. Minimize the blast radius:

- Extract subviews so only the part that depends on changed state re-renders.
- With `@Observable` (iOS 17+), SwiftUI tracks per-property access. Only views reading a changed property re-render.
- Avoid reading state you do not use in a given view's `body`.

```swift
// Bad: entire view re-renders when any property changes
struct MonolithicView: View {
    @State private var viewModel = DashboardViewModel()

    var body: some View {
        VStack {
            // This reads viewModel.header and viewModel.items and viewModel.footer
            Text(viewModel.header)
            ForEach(viewModel.items) { item in ItemRow(item: item) }
            Text(viewModel.footer)
        }
    }
}

// Better: split into subviews, each reading only what it needs
struct DashboardView: View {
    @State private var viewModel = DashboardViewModel()

    var body: some View {
        VStack {
            HeaderView(viewModel: viewModel)
            ItemListView(viewModel: viewModel)
            FooterView(viewModel: viewModel)
        }
    }
}

struct HeaderView: View {
    let viewModel: DashboardViewModel
    var body: some View {
        Text(viewModel.header) // Only re-renders when .header changes
    }
}
```

### Equatable Conformance
---

For views with complex inputs, conform to `Equatable` to give SwiftUI a fast equality check and skip unnecessary `body` evaluations.

```swift
struct ExpensiveRow: View, Equatable {
    let item: Item
    let isHighlighted: Bool

    static func == (lhs: ExpensiveRow, rhs: ExpensiveRow) -> Bool {
        lhs.item.id == rhs.item.id &&
        lhs.item.modifiedDate == rhs.item.modifiedDate &&
        lhs.isHighlighted == rhs.isHighlighted
    }

    var body: some View {
        // Complex layout that is expensive to evaluate
        HStack {
            AsyncImage(url: item.imageURL) { image in
                image.resizable().scaledToFill()
            } placeholder: {
                ProgressView()
            }
            .frame(width: 60, height: 60)

            VStack(alignment: .leading) {
                Text(item.title).font(.headline)
                Text(item.subtitle).font(.subheadline)
            }
        }
        .background(isHighlighted ? Color.yellow.opacity(0.2) : .clear)
    }
}
```

### Lazy Containers
---

- Use `LazyVStack`, `LazyHStack`, `LazyVGrid`, `LazyHGrid` for large collections. They create child views on demand.
- Regular `VStack` / `HStack` create all children immediately, which is fine for small, fixed sets.
- `List` is inherently lazy.

### .task Lifecycle
---

`.task` is the preferred way to tie async work to a view's lifecycle. It starts when the view appears and cancels automatically when the view disappears.

```swift
struct UserProfileView: View {
    @State private var viewModel = ProfileViewModel()

    var body: some View {
        content
            .task {
                // Cancelled automatically if the view disappears
                await viewModel.loadProfile()
            }
            .task(id: viewModel.userID) {
                // Re-runs when userID changes; previous task is cancelled
                await viewModel.loadProfile()
            }
            .refreshable {
                await viewModel.loadProfile()
            }
    }
}
```

### Measuring and Debugging
---

- Use Instruments (SwiftUI template) to profile view body evaluations.
- Add `Self._printChanges()` inside `body` during development to see what triggers re-renders:

```swift
var body: some View {
    #if DEBUG
    let _ = Self._printChanges() // Prints which properties changed
    #endif
    // ... actual view content
}
```

- Check the Xcode debug bar for view hierarchy depth and update counts.

### Summary of Performance Rules

| Rule | Why |
|---|---|
| Extract subviews | Limits re-render scope |
| Use `@Observable` over `ObservableObject` | Per-property tracking, fewer redraws |
| Use lazy containers for large lists | On-demand view creation |
| Use `.task` over `onAppear` + manual `Task` | Automatic cancellation |
| Conform to `Equatable` for expensive rows | Skips `body` when inputs haven't changed |
| Avoid `GeometryReader` in scroll content | Forces eager layout; use sparingly |
| Use `@State` for view-local state | Avoids over-scoping observation |
| Profile with Instruments | Measure before optimizing |
