# UIKit Interop Reference

Patterns for bridging UIKit and SwiftUI. Use UIKit only when SwiftUI lacks the capability. Target: Swift 6+ / iOS 17+.

## UIViewRepresentable

Wraps a UIKit `UIView` for use inside SwiftUI.

### Lifecycle

```
makeUIView  -->  updateUIView (called on every SwiftUI state change)  -->  dismantleUIView
                      ^                                                        |
                      |--- Coordinator handles delegates/actions --------------|
```

### Basic Example

```swift
import SwiftUI
import MapKit

struct MapView: UIViewRepresentable {
    var coordinate: CLLocationCoordinate2D

    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator
        return mapView
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        let region = MKCoordinateRegion(
            center: coordinate,
            span: MKCoordinateSpan(latitudeDelta: 0.05, longitudeDelta: 0.05)
        )
        mapView.setRegion(region, animated: context.transaction.animation != nil)
    }

    static func dismantleUIView(_ mapView: MKMapView, coordinator: Coordinator) {
        mapView.delegate = nil
        mapView.removeAnnotations(mapView.annotations)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    class Coordinator: NSObject, MKMapViewDelegate {
        func mapView(_ mapView: MKMapView, didSelect annotation: any MKAnnotation) {
            // Handle annotation selection
        }
    }
}
```

### Coordinator Pattern

The Coordinator bridges UIKit delegate/target-action callbacks back to SwiftUI. It is created once via `makeCoordinator()` and lives for the lifetime of the representable.

```swift
struct RatingSlider: UIViewRepresentable {
    @Binding var value: Float

    func makeUIView(context: Context) -> UISlider {
        let slider = UISlider()
        slider.minimumValue = 0
        slider.maximumValue = 5
        slider.addTarget(
            context.coordinator,
            action: #selector(Coordinator.valueChanged(_:)),
            for: .valueChanged
        )
        return slider
    }

    func updateUIView(_ slider: UISlider, context: Context) {
        slider.value = value
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(value: $value)
    }

    class Coordinator: NSObject {
        var value: Binding<Float>

        init(value: Binding<Float>) {
            self.value = value
        }

        @objc func valueChanged(_ sender: UISlider) {
            value.wrappedValue = sender.value
        }
    }
}
```

### Key Rules

- `makeUIView` is called **once**. Do all setup here (create view, set delegates, add targets).
- `updateUIView` is called on **every** SwiftUI state change that affects this view. Keep it idempotent -- set properties, do not create new subviews.
- `dismantleUIView` is **static**. Use it to clean up observers, delegates, or heavy resources.
- Store the `@Binding` reference in the Coordinator, not in closures, to avoid retain cycles.
- Use `context.transaction.animation` to detect whether SwiftUI is animating the change.
- Use `context.environment` to read SwiftUI environment values (color scheme, layout direction, etc.).

### Sizing

By default, UIKit views in SwiftUI take whatever size SwiftUI proposes. Override intrinsic content size or use `.frame()` / `.fixedSize()` to control layout.

```swift
struct IntrinsicSizeLabel: UIViewRepresentable {
    var text: String

    func makeUIView(context: Context) -> UILabel {
        let label = UILabel()
        label.setContentHuggingPriority(.required, for: .horizontal)
        label.setContentCompressionResistancePriority(.required, for: .horizontal)
        return label
    }

    func updateUIView(_ label: UILabel, context: Context) {
        label.text = text
    }
}
```


## UIViewControllerRepresentable

Wraps a full `UIViewController` for use in SwiftUI. Same lifecycle pattern as `UIViewRepresentable`.

### Camera (UIImagePickerController)

```swift
struct CameraPicker: UIViewControllerRepresentable {
    @Binding var image: UIImage?
    @Environment(\.dismiss) private var dismiss

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ picker: UIImagePickerController, context: Context) {
        // No updates needed -- camera configuration is set once
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: CameraPicker

        init(parent: CameraPicker) {
            self.parent = parent
        }

        func imagePickerController(
            _ picker: UIImagePickerController,
            didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]
        ) {
            parent.image = info[.originalImage] as? UIImage
            parent.dismiss()
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            parent.dismiss()
        }
    }
}
```

### Document Picker

```swift
import UniformTypeIdentifiers

struct DocumentPicker: UIViewControllerRepresentable {
    var contentTypes: [UTType]
    var onPick: ([URL]) -> Void

    func makeUIViewController(context: Context) -> UIDocumentPickerViewController {
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: contentTypes)
        picker.allowsMultipleSelection = true
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ vc: UIDocumentPickerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onPick: onPick)
    }

    class Coordinator: NSObject, UIDocumentPickerDelegate {
        let onPick: ([URL]) -> Void

        init(onPick: @escaping ([URL]) -> Void) {
            self.onPick = onPick
        }

        func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
            onPick(urls)
        }
    }
}
```

### Mail Compose

```swift
import MessageUI

struct MailComposer: UIViewControllerRepresentable {
    var recipients: [String]
    var subject: String
    var body: String
    var onResult: (MFMailComposeResult) -> Void

    static var canSendMail: Bool { MFMailComposeViewController.canSendMail() }

    func makeUIViewController(context: Context) -> MFMailComposeViewController {
        let vc = MFMailComposeViewController()
        vc.setToRecipients(recipients)
        vc.setSubject(subject)
        vc.setMessageBody(body, isHTML: false)
        vc.mailComposeDelegate = context.coordinator
        return vc
    }

    func updateUIViewController(_ vc: MFMailComposeViewController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(onResult: onResult)
    }

    class Coordinator: NSObject, MFMailComposeViewControllerDelegate {
        let onResult: (MFMailComposeResult) -> Void

        init(onResult: @escaping (MFMailComposeResult) -> Void) {
            self.onResult = onResult
        }

        func mailComposeController(
            _ controller: MFMailComposeViewController,
            didFinishWith result: MFMailComposeResult,
            error: Error?
        ) {
            onResult(result)
            controller.dismiss(animated: true)
        }
    }
}
```

### Key Rules

- Use `@Environment(\.dismiss)` in the representable to dismiss presented controllers cleanly.
- Controller creation happens in `makeUIViewController` -- do not re-create in `updateUIViewController`.
- For controllers that present modally (mail, camera), use `.sheet` or `.fullScreenCover` in SwiftUI.


## Hosting SwiftUI in UIKit

Use `UIHostingController` to embed SwiftUI views inside UIKit view hierarchies.

### Presenting a SwiftUI View

```swift
let settingsView = SettingsView(store: settingsStore)
let hostingController = UIHostingController(rootView: settingsView)

// Present modally
navigationController?.present(hostingController, animated: true)

// Or push onto navigation stack
navigationController?.pushViewController(hostingController, animated: true)
```

### Embedding as a Child View Controller

```swift
class DashboardViewController: UIViewController {
    private var hostingController: UIHostingController<StatsView>?

    override func viewDidLoad() {
        super.viewDidLoad()

        let statsView = StatsView(viewModel: statsViewModel)
        let hosting = UIHostingController(rootView: statsView)

        addChild(hosting)
        view.addSubview(hosting.view)
        hosting.didMove(toParent: self)

        hosting.view.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            hosting.view.topAnchor.constraint(equalTo: headerView.bottomAnchor),
            hosting.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            hosting.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            hosting.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])

        self.hostingController = hosting
    }

    func updateStats(with viewModel: StatsViewModel) {
        hostingController?.rootView = StatsView(viewModel: viewModel)
    }
}
```

### Sizing Considerations

```swift
// Let SwiftUI determine the size (useful for cells, headers)
let hosting = UIHostingController(rootView: BadgeView(count: 5))
hosting.sizingOptions = .intrinsicContentSize  // iOS 16+

// Get the preferred size for a given width
let targetSize = CGSize(width: 320, height: UIView.layoutFittingCompressedSize.height)
let fittingSize = hosting.sizeThatFits(in: targetSize)
```

### In UITableView / UICollectionView Cells

```swift
// iOS 16+ — use UIHostingConfiguration for SwiftUI-powered cells
class ModernCell: UICollectionViewCell {
    func configure(with item: Item) {
        contentConfiguration = UIHostingConfiguration {
            ItemRow(item: item)
        }
        .margins(.horizontal, 16)
    }
}
```

This is the preferred approach for new code. Avoids manual child view controller management inside cells.


## Navigation Interop

### Mixing UINavigationController with SwiftUI

When a UIKit app adopts SwiftUI incrementally, you often need SwiftUI screens inside a `UINavigationController` stack.

```swift
// Push a SwiftUI view onto a UIKit navigation stack
func showProfile(user: User) {
    let profileView = ProfileView(user: user)
    let hostingController = UIHostingController(rootView: profileView)
    hostingController.title = user.name
    hostingController.navigationItem.largeTitleDisplayMode = .never
    navigationController?.pushViewController(hostingController, animated: true)
}
```

### Passing Data Between UIKit and SwiftUI

Use `@Observable` view models shared between both worlds.

```swift
@Observable
class OrderViewModel {
    var items: [OrderItem] = []
    var total: Decimal { items.reduce(0) { $0 + $1.price } }

    func submit() async throws { /* ... */ }
}

// UIKit side — owns the view model
class OrderFlowCoordinator {
    let viewModel = OrderViewModel()

    func showCart(in nav: UINavigationController) {
        let cartView = CartView(viewModel: viewModel)
        let hosting = UIHostingController(rootView: cartView)
        nav.pushViewController(hosting, animated: true)
    }

    func showCheckout(in nav: UINavigationController) {
        let checkoutVC = CheckoutViewController(viewModel: viewModel)
        nav.pushViewController(checkoutVC, animated: true)
    }
}

// SwiftUI side — reads the same view model
struct CartView: View {
    var viewModel: OrderViewModel

    var body: some View {
        List(viewModel.items) { item in
            Text(item.name)
        }
    }
}
```

### Coordinator Pattern for Mixed Navigation

```swift
protocol Coordinator: AnyObject {
    var navigationController: UINavigationController { get }
    func start()
}

class AppCoordinator: Coordinator {
    let navigationController: UINavigationController

    init(navigationController: UINavigationController) {
        self.navigationController = navigationController
    }

    func start() {
        // UIKit screen
        let homeVC = HomeViewController()
        homeVC.onSettingsTapped = { [weak self] in
            self?.showSettings()
        }
        navigationController.pushViewController(homeVC, animated: false)
    }

    private func showSettings() {
        // SwiftUI screen pushed onto UIKit nav stack
        let settingsView = SettingsView(onDone: { [weak self] in
            self?.navigationController.popViewController(animated: true)
        })
        let hosting = UIHostingController(rootView: settingsView)
        navigationController.pushViewController(hosting, animated: true)
    }
}
```

### Key Rules

- Avoid nesting `NavigationStack` inside a `UINavigationController` -- use one navigation container or the other for a given flow.
- When SwiftUI views are pushed onto a UIKit nav stack, set `title` and `navigationItem` properties on the `UIHostingController` directly.
- For callback-based dismissal, pass closures from the coordinator into SwiftUI views rather than relying on `@Environment(\.dismiss)`.


## When to Use UIKit

### Decision Guide

| Need | Recommendation |
|------|---------------|
| Standard UI (lists, forms, navigation) | SwiftUI |
| Rich text editing (`NSAttributedString`, text attachments) | UIKit (`UITextView`) |
| Complex collection layouts (compositional, self-sizing cells with many edge cases) | UIKit (`UICollectionViewCompositionalLayout`) |
| Camera / barcode scanning | UIKit (`AVCaptureSession`, `UIImagePickerController`) |
| Custom gesture recognizer subclasses | UIKit |
| Drag-and-drop with fine-grained control | UIKit |
| MapKit with heavy annotation customization | UIKit (`MKMapView`) |
| WebView with navigation delegates | UIKit (`WKWebView`) |
| Existing large UIKit codebase | Keep UIKit, migrate incrementally |
| PDF rendering and annotation | UIKit (`PDFKit`) |
| In-app mail / message compose | UIKit (`MFMailComposeViewController`) |
| Complex keyboard management (input accessories, custom inputs) | UIKit |
| Accessibility requiring `UIAccessibilityCustomAction` fine-tuning | UIKit |

### Capabilities SwiftUI Still Lacks or Has Limited Support For (as of iOS 17/18)

- **`UITextView` equivalent with full attributed string support** -- SwiftUI `TextEditor` is basic; no inline images, no link taps, no custom `NSTextStorage`.
- **First responder management** -- `@FocusState` covers common cases but does not support programmatic first responder resignation in all contexts.
- **Custom input views and input accessory views** -- no SwiftUI API for replacing the keyboard with a custom view.
- **Fine-grained scroll view control** -- `ScrollViewReader` lacks scroll deceleration rate, content inset, and pull-to-refresh customization at the UIKit level.
- **`UICollectionView` compositional layout** -- SwiftUI `Grid` and `LazyVGrid`/`LazyHGrid` do not match the power of `NSCollectionLayoutSection` with orthogonal scrolling, estimated dimensions, and supplementary views.
- **Subclassing views or view controllers** for advanced lifecycle hooks.


## Migration Strategy

### Incremental Migration from UIKit to SwiftUI

Migrate screen by screen, not all at once. A typical sequence:

```
Phase 1: Leaf screens (Settings, Profile, About)
    |
Phase 2: List/detail screens with shared view models
    |
Phase 3: Complex flows (onboarding, checkout)
    |
Phase 4: Navigation layer (replace UINavigationController with NavigationStack)
    |
Phase 5: App entry point (replace UIApplicationDelegate with @main App)
```

### Shared ViewModel Layer

Keep view models framework-agnostic so both UIKit and SwiftUI screens can use them during migration.

```swift
// Works with both UIKit and SwiftUI
@Observable
@MainActor
class ProfileViewModel {
    private let userService: UserService

    var user: User?
    var errorMessage: String?

    init(userService: UserService) {
        self.userService = userService
    }

    func load() async {
        do {
            user = try await userService.fetchCurrentUser()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// SwiftUI consumption
struct ProfileView: View {
    var viewModel: ProfileViewModel

    var body: some View {
        if let user = viewModel.user {
            Text(user.name)
        }
    }
}

// UIKit consumption
class ProfileViewController: UIViewController {
    private let viewModel: ProfileViewModel
    private var observationTask: Task<Void, Never>?

    init(viewModel: ProfileViewModel) {
        self.viewModel = viewModel
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { fatalError("Use init(viewModel:)") }

    override func viewDidLoad() {
        super.viewDidLoad()
        // Note: iOS 26+ provides updateProperties() for automatic @Observable tracking.
        // For pre-iOS 26, use withObservationTracking with continuation-based re-registration:
        observationTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                await withCheckedContinuation { continuation in
                    withObservationTracking {
                        self.updateUI(with: self.viewModel.user)
                    } onChange: {
                        continuation.resume()
                    }
                }
            }
        }
        Task { await viewModel.load() }
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        observationTask?.cancel()
    }

    private func updateUI(with user: User?) {
        title = user?.name ?? "Profile"
    }
}
```

### Screen-by-Screen Approach

1. **Identify the screen** with fewest UIKit-specific dependencies.
2. **Extract the view model** (if not already separated). Ensure it does not import UIKit.
3. **Build the SwiftUI view** using the same view model.
4. **Replace the UIKit screen** with `UIHostingController` wrapping the new SwiftUI view.
5. **Verify navigation, data flow, and deep links** still work.
6. **Remove the old UIKit view controller** once the new screen is stable.

### Key Rules

- Do not attempt a "big bang" rewrite. Ship incremental migrations behind the same navigation structure.
- Keep the Coordinator or Router layer in UIKit until the majority of screens are SwiftUI.
- If the app uses `UIAppearance` heavily, be aware that SwiftUI views inside `UIHostingController` respect appearance proxies, but SwiftUI-native styling (`.tint`, `.foregroundStyle`) takes precedence.
- Run UI tests after each screen migration to catch layout and behavior regressions.


## AppKit Interop (macOS)

For cross-platform awareness. The patterns mirror UIKit interop.

### NSViewRepresentable

```swift
import SwiftUI
import AppKit

struct NativeTextField: NSViewRepresentable {
    @Binding var text: String

    func makeNSView(context: Context) -> NSTextField {
        let textField = NSTextField()
        textField.delegate = context.coordinator
        return textField
    }

    func updateNSView(_ textField: NSTextField, context: Context) {
        textField.stringValue = text
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text)
    }

    class Coordinator: NSObject, NSTextFieldDelegate {
        var text: Binding<String>

        init(text: Binding<String>) {
            self.text = text
        }

        func controlTextDidChange(_ notification: Notification) {
            guard let textField = notification.object as? NSTextField else { return }
            text.wrappedValue = textField.stringValue
        }
    }
}
```

### NSViewControllerRepresentable

Same structure as `UIViewControllerRepresentable`. Use for wrapping AppKit view controllers that have no SwiftUI equivalent.

```swift
struct PDFViewer: NSViewControllerRepresentable {
    var document: PDFDocument

    func makeNSViewController(context: Context) -> PDFViewController {
        let vc = PDFViewController()
        vc.pdfView.document = document
        return vc
    }

    func updateNSViewController(_ vc: PDFViewController, context: Context) {
        vc.pdfView.document = document
    }
}
```

### NSHostingController / NSHostingView

```swift
// Embed SwiftUI in an AppKit window
let hostingView = NSHostingView(rootView: ContentView())
window.contentView = hostingView

// Or use as a view controller
let hostingController = NSHostingController(rootView: SettingsView())
window.contentViewController = hostingController
```

### Platform Mapping

| UIKit | AppKit | SwiftUI Wrapper |
|-------|--------|-----------------|
| `UIViewRepresentable` | `NSViewRepresentable` | Same protocol shape |
| `UIViewControllerRepresentable` | `NSViewControllerRepresentable` | Same protocol shape |
| `UIHostingController` | `NSHostingController` / `NSHostingView` | Embed SwiftUI |
| `UIView` | `NSView` | -- |
| `UIViewController` | `NSViewController` | -- |


## Common Pitfalls

### Memory Management

```swift
// BAD: Strong reference cycle -- coordinator captures self, self holds coordinator
class Coordinator: NSObject {
    let parent: MyRepresentable  // Strong reference to the representable struct
    // This is actually fine for structs (value type), but be careful with closures:
}

// BAD: Closure capturing self strongly
func makeUIView(context: Context) -> UIView {
    let view = CustomView()
    view.onTap = { [self] in    // Captures the struct, potentially stale
        self.handleTap()
    }
    return view
}

// GOOD: Route callbacks through the coordinator
func makeUIView(context: Context) -> UIView {
    let view = CustomView()
    view.onTap = { [weak coordinator = context.coordinator] in
        coordinator?.handleTap()
    }
    return view
}
```

Rules:
- `UIViewRepresentable` is a **struct** (value type), so capturing `self` creates a copy. Mutations won't propagate. Always use the Coordinator for callbacks.
- When the Coordinator holds closures referencing UIKit objects, use `[weak view]` to avoid retaining the view.
- Cancel any `Task` instances stored in the Coordinator during `dismantleUIView`.

### Update Cycles

```swift
// BAD: Triggering state changes inside updateUIView causes infinite loops
func updateUIView(_ textView: UITextView, context: Context) {
    textView.text = text
    text = textView.text  // Writes back to @Binding -- triggers updateUIView again
}

// GOOD: Guard against redundant updates
func updateUIView(_ textView: UITextView, context: Context) {
    if textView.text != text {
        textView.text = text
    }
}

// GOOD: Use a flag in the coordinator to skip programmatic updates
func updateUIView(_ textView: UITextView, context: Context) {
    guard !context.coordinator.isUpdatingFromUIKit else { return }
    textView.text = text
}
```

Rules:
- Never write to `@Binding` inside `updateUIView` / `updateUIViewController`. Changes flow **from** SwiftUI **to** UIKit in `updateUIView`, and **from** UIKit **to** SwiftUI via Coordinator delegate methods.
- Use equality checks or coordinator flags to break potential update cycles.

### Keyboard Handling

```swift
// Problem: UIKit text views inside SwiftUI don't always respect @FocusState

// Workaround: Manage first responder manually via coordinator
struct FocusableTextField: UIViewRepresentable {
    @Binding var text: String
    @Binding var isFocused: Bool

    func makeUIView(context: Context) -> UITextField {
        let tf = UITextField()
        tf.delegate = context.coordinator
        return tf
    }

    func updateUIView(_ tf: UITextField, context: Context) {
        tf.text = text
        if isFocused && !tf.isFirstResponder {
            // Delay to avoid interfering with SwiftUI's layout pass
            DispatchQueue.main.async { tf.becomeFirstResponder() }
        } else if !isFocused && tf.isFirstResponder {
            tf.resignFirstResponder()
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text, isFocused: $isFocused)
    }

    class Coordinator: NSObject, UITextFieldDelegate {
        var text: Binding<String>
        var isFocused: Binding<Bool>

        init(text: Binding<String>, isFocused: Binding<Bool>) {
            self.text = text
            self.isFocused = isFocused
        }

        func textFieldDidChangeSelection(_ textField: UITextField) {
            text.wrappedValue = textField.text ?? ""
        }

        func textFieldDidBeginEditing(_ textField: UITextField) {
            isFocused.wrappedValue = true
        }

        func textFieldDidEndEditing(_ textField: UITextField) {
            isFocused.wrappedValue = false
        }
    }
}
```

### Safe Area Differences

```swift
// UIHostingController respects safe areas by default.
// To disable safe area behavior (e.g., edge-to-edge content):
let hosting = UIHostingController(rootView: contentView)
hosting.safeAreaRegions = []  // iOS 16.4+ -- removes all safe area insets

// When embedding a UIView in SwiftUI, the UIKit view receives
// safe area insets from SwiftUI's container. If your UIKit view
// handles safe areas internally, you may see double insets.

// Fix: Tell the hosting controller to ignore safe areas, or
// configure the UIKit view to not add its own safe area handling.
```

### Other Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Dark mode not updating | UIKit view ignores `traitCollection` changes | Read `context.environment.colorScheme` in `updateUIView` and apply |
| Animations not matching | UIKit and SwiftUI animate independently | Use `context.transaction.animation` to detect SwiftUI animations and call `UIView.animate` with matching parameters |
| Auto Layout warnings | Missing constraints on hosted views | Always set `translatesAutoresizingMaskIntoConstraints = false` and activate constraints |
| Dynamic Type not working | UIKit view uses fixed font sizes | Use `UIFont.preferredFont(forTextStyle:)` and read `context.environment.dynamicTypeSize` |
| View not resizing on rotation | Hosting controller not in view hierarchy properly | Ensure `addChild` / `didMove(toParent:)` lifecycle is correct |
