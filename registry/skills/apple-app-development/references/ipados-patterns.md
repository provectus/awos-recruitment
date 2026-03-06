# iPadOS Patterns

## Multitasking

iPadOS supports Split View, Slide Over, and Stage Manager. Apps must handle dynamic size changes by reading the horizontal size class and adapting layout accordingly.

### Size class adaptation

```swift
struct AdaptiveView: View {
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        if horizontalSizeClass == .compact {
            TabView {
                ContentListView()
                DetailView()
            }
        } else {
            NavigationSplitView {
                ContentListView()
            } detail: {
                DetailView()
            }
        }
    }
}
```

### Responding to size changes

Use `GeometryReader` or `ViewThatFits` to adapt to arbitrary frame sizes in multitasking contexts:

```swift
struct FlexibleGrid: View {
    var body: some View {
        ViewThatFits(in: .horizontal) {
            // Preferred: wide layout
            HStack(spacing: 16) {
                PrimaryPanel()
                SecondaryPanel()
                TertiaryPanel()
            }
            // Fallback: stacked layout
            VStack(spacing: 12) {
                PrimaryPanel()
                SecondaryPanel()
            }
        }
    }
}
```

### Stage Manager

Stage Manager uses resizable windows. Declare support in your scene:

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        // Stage Manager respects default and minimum sizes
        .defaultSize(width: 800, height: 600)
    }
}
```

Rules:
- Never assume a fixed screen size. Always use adaptive layout.
- Test in all multitasking modes: full screen, Split View (1/3, 1/2, 2/3), Slide Over, Stage Manager.
- Avoid hardcoded widths. Prefer flexible layouts with `flexible()`, `adaptive(minimum:)` grid items, or `ViewThatFits`.

## Pointer and Keyboard Support

### Hover effects

Apply system hover effects to interactive elements. The system automatically provides a lift, highlight, or automatic effect:

```swift
struct ToolbarButton: View {
    let icon: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: icon)
                .frame(width: 44, height: 44)
        }
        .hoverEffect(.highlight)
    }
}
```

Available hover effect styles:
- `.automatic` — system decides lift or highlight based on context
- `.highlight` — subtle highlight overlay
- `.lift` — element lifts with a shadow

### Custom pointer shape

```swift
Text("Resizable Edge")
    .onContinuousHover { phase in
        switch phase {
        case .active(let location):
            // Track pointer location if needed
            break
        case .ended:
            break
        }
    }
    .pointerStyle(.horizontalResize)
```

### Keyboard shortcuts

Add keyboard shortcuts to buttons and commands:

```swift
struct DocumentView: View {
    @State private var showInspector = false

    var body: some View {
        ContentEditor()
            .toolbar {
                Button("Inspector") {
                    showInspector.toggle()
                }
                .keyboardShortcut("i", modifiers: [.command, .option])
            }
    }
}
```

### App-level keyboard commands

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .commands {
            CommandMenu("Document") {
                Button("Export PDF") { exportPDF() }
                    .keyboardShortcut("e", modifiers: [.command, .shift])

                Button("Print") { printDocument() }
                    .keyboardShortcut("p", modifiers: .command)
            }
        }
    }
}
```

### Hardware keyboard navigation

Enable full keyboard navigation by supporting focus-based interaction:

```swift
struct ItemList: View {
    @FocusState private var focusedItem: Item.ID?
    let items: [Item]

    var body: some View {
        List(items) { item in
            ItemRow(item: item)
                .focused($focusedItem, equals: item.id)
        }
        .onMoveCommand { direction in
            // Handle arrow key navigation
            handleMove(direction)
        }
    }
}
```

Rules:
- Add `.hoverEffect()` to all tappable elements. Pointer users expect visual feedback.
- Provide keyboard shortcuts for frequent actions. Follow platform conventions (Cmd+C, Cmd+V, etc.).
- Support Tab key navigation for form-heavy interfaces with `@FocusState`.

## Drag and Drop

### Transferable protocol

Define how your models transfer across drag and drop boundaries:

```swift
struct PhotoItem: Identifiable, Codable, Transferable {
    let id: UUID
    let title: String
    let imageData: Data

    static var transferRepresentation: some TransferRepresentation {
        CodableRepresentation(contentType: .photoItem)
        DataRepresentation(exportedContentType: .jpeg) { item in
            item.imageData
        }
        ProxyRepresentation(exporting: \.title)  // Fallback: plain text
    }
}

// Declare custom UTType
extension UTType {
    static let photoItem = UTType(exportedAs: "com.example.photoitem")
}
```

### Draggable views

```swift
struct PhotoGrid: View {
    let photos: [PhotoItem]

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 120))]) {
            ForEach(photos) { photo in
                PhotoThumbnail(photo: photo)
                    .draggable(photo) {
                        // Custom drag preview
                        PhotoThumbnail(photo: photo)
                            .frame(width: 100, height: 100)
                            .shadow(radius: 4)
                    }
            }
        }
    }
}
```

### Drop destination

```swift
struct AlbumView: View {
    @State private var albumPhotos: [PhotoItem] = []

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 120))]) {
            ForEach(albumPhotos) { photo in
                PhotoThumbnail(photo: photo)
            }
        }
        .dropDestination(for: PhotoItem.self) { items, location in
            albumPhotos.append(contentsOf: items)
            return true
        } isTargeted: { isTargeted in
            // Highlight drop zone
        }
    }
}
```

### Multi-item drag with reordering

```swift
struct ReorderableList: View {
    @State private var items: [TaskItem] = []
    @State private var selection: Set<TaskItem.ID> = []

    var body: some View {
        List(selection: $selection) {
            ForEach(items) { item in
                TaskRow(item: item)
                    .draggable(item)
            }
            .onMove { from, to in
                items.move(fromOffsets: from, toOffset: to)
            }
        }
        .dropDestination(for: TaskItem.self) { items, offset in
            self.items.insert(contentsOf: items, at: offset)
        }
    }
}
```

### Accepting external content (images, files)

```swift
struct ImportView: View {
    @State private var importedImages: [Image] = []

    var body: some View {
        ContentArea()
            .dropDestination(for: Data.self) { items, location in
                for data in items {
                    if let uiImage = UIImage(data: data) {
                        importedImages.append(Image(uiImage: uiImage))
                    }
                }
                return !items.isEmpty
            }
    }
}
```

Rules:
- Implement `Transferable` on any model type that participates in drag and drop.
- Provide multiple representations (codable, data, proxy) for maximum interoperability with other apps.
- Always provide a drag preview that is smaller than the original view.
- Return `true` from drop handler only if the drop was accepted.

## Sidebar Navigation

### Two-column layout

```swift
struct TwoColumnApp: View {
    @State private var selectedFolder: Folder?

    var body: some View {
        NavigationSplitView {
            List(folders, selection: $selectedFolder) { folder in
                Label(folder.name, systemImage: folder.icon)
            }
            .navigationTitle("Folders")
        } detail: {
            if let folder = selectedFolder {
                FolderDetailView(folder: folder)
            } else {
                ContentUnavailableView("Select a Folder",
                    systemImage: "folder",
                    description: Text("Choose a folder from the sidebar"))
            }
        }
    }
}
```

### Three-column layout

```swift
struct ThreeColumnApp: View {
    @State private var selectedMailbox: Mailbox?
    @State private var selectedMessage: Message?

    var body: some View {
        NavigationSplitView {
            // Sidebar
            List(mailboxes, selection: $selectedMailbox) { mailbox in
                Label(mailbox.name, systemImage: mailbox.icon)
            }
            .navigationTitle("Mail")
        } content: {
            // Content list
            if let mailbox = selectedMailbox {
                List(mailbox.messages, selection: $selectedMessage) { message in
                    MessageRow(message: message)
                }
                .navigationTitle(mailbox.name)
            }
        } detail: {
            // Detail
            if let message = selectedMessage {
                MessageDetailView(message: message)
            } else {
                ContentUnavailableView("No Message Selected",
                    systemImage: "envelope")
            }
        }
    }
}
```

### Controlling column visibility and width

```swift
struct AdaptiveNavigation: View {
    @State private var columnVisibility: NavigationSplitViewVisibility = .all
    @State private var preferredCompactColumn: NavigationSplitViewColumn = .sidebar

    var body: some View {
        NavigationSplitView(columnVisibility: $columnVisibility,
                            preferredCompactColumn: $preferredCompactColumn) {
            SidebarView()
        } content: {
            ContentListView()
        } detail: {
            DetailView()
        }
        .navigationSplitViewStyle(.balanced)
        // .prominentDetail makes the detail column take more space
    }
}
```

### Compact adaptation

On compact width (iPhone or narrow Split View), `NavigationSplitView` collapses into a stack. Control which column shows first with `preferredCompactColumn`:

```swift
NavigationSplitView(
    preferredCompactColumn: $preferredColumn
) {
    Sidebar()
} detail: {
    Detail()
}
// On compact: if preferredColumn == .sidebar, user sees sidebar first
// On compact: if preferredColumn == .detail, user sees detail first
```

Rules:
- Use `NavigationSplitView` for all iPad navigation. Avoid `NavigationStack` as the root on iPad unless the app is truly single-column.
- Always handle the empty state in the detail column with `ContentUnavailableView`.
- Test compact adaptation — verify the app works when `NavigationSplitView` collapses in narrow Split View.

## Pencil Support

### PencilKit canvas via UIViewRepresentable

```swift
import PencilKit

struct CanvasView: UIViewRepresentable {
    @Binding var canvasView: PKCanvasView
    @Binding var drawing: PKDrawing
    let toolPicker: PKToolPicker

    func makeUIView(context: Context) -> PKCanvasView {
        canvasView.tool = PKInkingTool(.pen, color: .black, width: 5)
        canvasView.drawingPolicy = .anyInput  // or .pencilOnly
        canvasView.delegate = context.coordinator
        canvasView.drawing = drawing
        canvasView.backgroundColor = .clear
        canvasView.isOpaque = false

        // Show tool picker
        toolPicker.setVisible(true, forFirstResponder: canvasView)
        toolPicker.addObserver(canvasView)
        canvasView.becomeFirstResponder()

        return canvasView
    }

    func updateUIView(_ uiView: PKCanvasView, context: Context) {
        // Update drawing if changed externally
        if uiView.drawing != drawing {
            uiView.drawing = drawing
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    class Coordinator: NSObject, PKCanvasViewDelegate {
        let parent: CanvasView

        init(_ parent: CanvasView) {
            self.parent = parent
        }

        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            parent.drawing = canvasView.drawing
        }
    }
}
```

### Using the canvas in SwiftUI

```swift
struct DrawingScreen: View {
    @State private var canvasView = PKCanvasView()
    @State private var drawing = PKDrawing()
    @State private var toolPicker = PKToolPicker()

    var body: some View {
        CanvasView(canvasView: $canvasView,
                   drawing: $drawing,
                   toolPicker: toolPicker)
            .ignoresSafeArea()
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button("Clear") {
                        drawing = PKDrawing()
                    }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button("Undo") {
                        canvasView.undoManager?.undo()
                    }
                }
            }
    }
}
```

### Pencil hover detection (iPad Pro with Apple Pencil 2nd gen+)

```swift
struct HoverAwareCanvas: UIViewRepresentable {
    func makeUIView(context: Context) -> PKCanvasView {
        let canvas = PKCanvasView()

        // Pencil hover interaction (iPadOS 16.1+)
        let hoverInteraction = UIHoverGestureRecognizer(
            target: context.coordinator,
            action: #selector(Coordinator.handleHover(_:))
        )
        canvas.addGestureRecognizer(hoverInteraction)

        return canvas
    }

    func updateUIView(_ uiView: PKCanvasView, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator() }

    class Coordinator: NSObject {
        @objc func handleHover(_ recognizer: UIHoverGestureRecognizer) {
            let location = recognizer.location(in: recognizer.view)
            let altitude = recognizer.altitudeAngle
            let azimuth = recognizer.azimuthAngle(in: recognizer.view)

            switch recognizer.state {
            case .began, .changed:
                // Show preview cursor at location
                // altitude indicates distance from screen
                break
            case .ended, .cancelled:
                // Hide preview cursor
                break
            default:
                break
            }
        }
    }
}
```

Rules:
- Use `.pencilOnly` drawing policy when the app has finger-based gestures that conflict with drawing.
- Use `.anyInput` when the canvas is the primary interaction area.
- Always expose undo/redo when using PencilKit.
- Test with both Apple Pencil and finger input.

## Mac Catalyst

### Enabling Mac Catalyst

In Xcode: select your target > General > Deployment Info > check "Mac (Designed for iPad)" or "Mac (Mac Catalyst)".

There are two scaling modes:
- **"Designed for iPad"** — pixel-perfect iPad app in a fixed window on Mac. Minimal effort, limited Mac features.
- **"Mac Catalyst" (scaled/optimized)** — runs as a proper Mac app. Access to AppKit behaviors, menu bar, resizable windows.

### Detecting Mac Catalyst at runtime

```swift
struct PlatformAdaptiveView: View {
    var body: some View {
        VStack {
            #if targetEnvironment(macCatalyst)
            Text("Running on Mac via Catalyst")
                .font(.title2)
            #else
            Text("Running on iPad")
                .font(.title2)
            #endif
        }
    }
}
```

### Conditional code with ProcessInfo

```swift
extension ProcessInfo {
    /// True when running as Mac Catalyst (not "Designed for iPad")
    var isMacCatalystApp: Bool {
        #if targetEnvironment(macCatalyst)
        return true
        #else
        return false
        #endif
    }

    /// True when running on Mac (either Catalyst or native)
    var isMacApp: Bool {
        #if os(macOS) || targetEnvironment(macCatalyst)
        return true
        #else
        return false
        #endif
    }
}
```

### Accessing AppKit via plugin bundle (advanced)

When you need AppKit APIs not available through Catalyst:

```swift
// In your Catalyst app, load a macOS bundle plugin
// 1. Create a macOS Bundle target (AppKitBridge.bundle)
// 2. Define a protocol both targets share

@objc protocol AppKitBridge {
    func setWindowLevel(_ level: Int)
    func enableWindowTabbing()
}

// 3. Load at runtime
#if targetEnvironment(macCatalyst)
if let bundle = Bundle(path: "/path/to/AppKitBridge.bundle"),
   bundle.load(),
   let bridgeClass = bundle.principalClass as? NSObject.Type {
    let bridge = bridgeClass.init() as? AppKitBridge
    bridge?.enableWindowTabbing()
}
#endif
```

### Mac Catalyst vs native macOS target

| Criteria | Mac Catalyst | Native macOS |
|---|---|---|
| Codebase | Shared with iPadOS | Separate or multiplatform |
| UI framework | SwiftUI + UIKit | SwiftUI + AppKit |
| Mac feel | Good with effort | Native |
| Menu bar | Supported via `.commands` | Full AppKit menus |
| Window management | Basic (improved in recent iPadOS) | Full NSWindow API |
| App Store | iOS + Mac from one binary | Separate Mac binary |
| Effort for iPad app | Low — flip a switch | High — port or rewrite |
| Best for | iPad-first apps needing Mac presence | Mac-first or complex Mac apps |

Rules:
- Use Mac Catalyst when your app is iPad-first and you want a Mac version with minimal effort.
- Use a native macOS target when you need deep AppKit integration, complex window management, or a Mac-first experience.
- Always test Catalyst apps on actual macOS. Simulator does not cover all Catalyst behaviors.
- Use `#if targetEnvironment(macCatalyst)` for platform-specific code, not `#if os(macOS)` (Catalyst is not `os(macOS)`).

## Desktop-Class iPad

iPadOS 16+ introduced desktop-class features: customizable toolbars, document-based app enhancements, find and replace, and integrated undo/redo.

### Customizable toolbar

```swift
struct DocumentEditor: View {
    var body: some View {
        TextEditor(text: $documentText)
            .toolbar(id: "editor-toolbar") {
                ToolbarItem(id: "bold", placement: .secondaryAction) {
                    Button(action: toggleBold) {
                        Label("Bold", systemImage: "bold")
                    }
                }
                ToolbarItem(id: "italic", placement: .secondaryAction) {
                    Button(action: toggleItalic) {
                        Label("Italic", systemImage: "italic")
                    }
                }
                ToolbarItem(id: "export", placement: .primaryAction) {
                    Button(action: exportDocument) {
                        Label("Export", systemImage: "square.and.arrow.up")
                    }
                }
            }
            .toolbarRole(.editor)  // Enables customization UI
    }
}
```

`.toolbarRole(.editor)` tells the system this is a content-editing toolbar. Users can customize which items appear and their order.

### Document-based apps

```swift
@main
struct MyDocumentApp: App {
    var body: some Scene {
        DocumentGroup(newDocument: { TextDocument() }) { config in
            TextDocumentEditor(document: config.$document)
        }
    }
}

struct TextDocument: FileDocument {
    static var readableContentTypes: [UTType] = [.plainText]
    var text: String = ""

    init() {}

    init(configuration: ReadConfiguration) throws {
        guard let data = configuration.file.regularFileContents,
              let string = String(data: data, encoding: .utf8) else {
            throw CocoaError(.fileReadCorruptFile)
        }
        text = string
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        guard let data = text.data(using: .utf8) else {
            throw CocoaError(.fileWriteUnknown)
        }
        return FileWrapper(regularFileWithContents: data)
    }
}
```

### Find and replace

SwiftUI provides built-in find and replace for `TextEditor`:

```swift
struct SearchableEditor: View {
    @State private var text = ""
    @State private var isSearching = false

    var body: some View {
        TextEditor(text: $text)
            .findNavigator(isPresented: $isSearching)
            .toolbar {
                Button("Find") {
                    isSearching.toggle()
                }
                .keyboardShortcut("f", modifiers: .command)
            }
    }
}
```

### Undo and redo

```swift
struct EditableView: View {
    @Environment(\.undoManager) private var undoManager
    @State private var items: [String] = []

    func addItem(_ item: String) {
        let previousItems = items
        items.append(item)

        undoManager?.registerUndo(withTarget: self) { _ in
            items = previousItems
        }
        undoManager?.setActionName("Add Item")
    }

    var body: some View {
        List(items, id: \.self) { item in
            Text(item)
        }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                Button(action: { undoManager?.undo() }) {
                    Label("Undo", systemImage: "arrow.uturn.backward")
                }
                .disabled(!(undoManager?.canUndo ?? false))

                Button(action: { undoManager?.redo() }) {
                    Label("Redo", systemImage: "arrow.uturn.forward")
                }
                .disabled(!(undoManager?.canRedo ?? false))
            }
        }
    }
}
```

Rules:
- Use `toolbar(id:)` with string IDs for customizable toolbars. Without an ID, toolbar items cannot be rearranged by the user.
- Use `.toolbarRole(.editor)` for content-editing interfaces.
- Expose undo/redo in document-editing apps. The system provides Cmd+Z / Cmd+Shift+Z automatically when `undoManager` is wired up.
- Use `.findNavigator()` for searchable text content instead of building custom find UI.

## External Display

### Multi-scene support

To support external displays, enable multi-scene support and manage separate scenes for each display.

In `Info.plist`, enable scene manifest:

```xml
<key>UIApplicationSupportsMultipleScenes</key>
<true/>
```

### Extending content to external display

```swift
@main
struct PresentationApp: App {
    var body: some Scene {
        WindowGroup {
            PresenterControlView()
        }

        // External display scene
        WindowGroup(id: "external-display") {
            ExternalDisplayView()
        }
    }
}
```

### Detecting and managing external screens with UIKit

```swift
@Observable
class ExternalDisplayManager {
    var externalScreen: UIScreen?
    var externalWindow: UIWindow?

    init() {
        observeScreenConnections()
    }

    private func observeScreenConnections() {
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(screenDidConnect),
            name: UIScreen.didConnectNotification,
            object: nil
        )
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(screenDidDisconnect),
            name: UIScreen.didDisconnectNotification,
            object: nil
        )

        // Check for already-connected screens
        if let screen = UIScreen.screens.dropFirst().first {
            configureExternalScreen(screen)
        }
    }

    @objc private func screenDidConnect(_ notification: Notification) {
        guard let screen = notification.object as? UIScreen else { return }
        configureExternalScreen(screen)
    }

    @objc private func screenDidDisconnect(_ notification: Notification) {
        externalWindow?.isHidden = true
        externalWindow = nil
        externalScreen = nil
    }

    private func configureExternalScreen(_ screen: UIScreen) {
        externalScreen = screen
        let window = UIWindow(frame: screen.bounds)
        window.screen = screen

        let hostingController = UIHostingController(
            rootView: ExternalDisplayView()
        )
        window.rootViewController = hostingController
        window.isHidden = false
        externalWindow = window
    }
}
```

### Scene-based external display (iPadOS 16+)

```swift
struct ExternalDisplayView: View {
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 24) {
                Text("Presentation Slide")
                    .font(.system(size: 64, weight: .bold))
                    .foregroundStyle(.white)
                Image("slide-content")
                    .resizable()
                    .scaledToFit()
            }
            .padding(48)
        }
    }
}
```

Rules:
- Enable `UIApplicationSupportsMultipleScenes` in `Info.plist` for external display support.
- Adapt content for the external screen resolution — do not mirror the iPad screen.
- Handle connect/disconnect gracefully. The external display can be removed at any time.
- External displays have no touch input. Ensure all interaction happens on the iPad screen.
- Test with both wired (USB-C/HDMI) and wireless (AirPlay) external displays.
