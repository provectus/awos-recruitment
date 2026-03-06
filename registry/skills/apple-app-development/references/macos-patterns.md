# macOS Patterns Reference

## Contents
- Window management (`WindowGroup`, `Window`, `openWindow`, sizing, resizability)
- Menu bar (`CommandMenu`, `CommandGroup`, keyboard shortcuts)
- Menu bar extra apps (`MenuBarExtra`, standalone menu bar apps)
- Toolbar (`.toolbar`, `ToolbarItem`, `ToolbarItemGroup`, customizable toolbars)
- Settings/Preferences (`Settings` scene, `@AppStorage`, tabbed preferences)
- AppKit interop (`NSViewRepresentable`, `NSViewControllerRepresentable`, `NSHostingController`)
- Sandboxing and entitlements (App Sandbox, file access, security-scoped bookmarks)
- Document-based apps (`DocumentGroup`, `FileDocument`, `ReferenceFileDocument`)
- Drag and drop — macOS-specific (file promises, pasteboard, `NSItemProvider`)
- Distribution (App Store, Developer ID, notarization, DMG/PKG)
- Differences from iOS (no UIKit, lifecycle, menu-driven UX, multi-window)

## Window Management

macOS apps are multi-window by default. SwiftUI provides several scene types for window management.

### WindowGroup — multiple identical windows

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .defaultSize(width: 800, height: 600)
        .windowResizability(.contentSize) // or .contentMinSize, .automatic
    }
}
```

### Window — single unique window

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }

        // A single-instance utility window
        Window("Activity Log", id: "activity-log") {
            ActivityLogView()
        }
        .defaultSize(width: 400, height: 300)
        .windowResizability(.contentMinSize)
        .defaultPosition(.trailing)
    }
}
```

### Opening windows programmatically

```swift
struct ContentView: View {
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Button("Show Activity Log") {
            openWindow(id: "activity-log")
        }
    }
}
```

### WindowGroup with value-based windows

```swift
// Define a window that opens for a specific value
WindowGroup("Detail", for: Item.ID.self) { $itemID in
    if let itemID {
        DetailView(itemID: itemID)
    }
}

// Open it
openWindow(value: selectedItem.id)
```

### Window sizing and position

```swift
WindowGroup {
    ContentView()
}
.defaultSize(width: 1000, height: 700)
.defaultPosition(.center)
.windowResizability(.contentSize)      // window fits content exactly
// .windowResizability(.contentMinSize) // content sets minimum, user can enlarge
// .windowResizability(.automatic)      // system decides (default)
```

### Anti-patterns

- **Forcing single-window behavior on `WindowGroup`** — use `Window` for single-instance windows, not hacks to prevent new instances.
- **Ignoring `windowResizability`** — without it, windows may resize to awkward dimensions. Always set an explicit policy.

## Menu Bar

macOS apps are menu-driven. SwiftUI lets you add and customize menu bar menus declaratively.

### Adding custom menus

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .commands {
            // Add a new top-level menu
            CommandMenu("Export") {
                Button("Export as PDF") {
                    exportPDF()
                }
                .keyboardShortcut("e", modifiers: [.command, .shift])

                Button("Export as PNG") {
                    exportPNG()
                }
                .keyboardShortcut("p", modifiers: [.command, .shift])

                Divider()

                Button("Export All...") {
                    exportAll()
                }
            }
        }
    }
}
```

### Modifying built-in menus with CommandGroup

```swift
.commands {
    // Insert before a built-in menu group
    CommandGroup(before: .newItem) {
        Button("New from Template...") {
            newFromTemplate()
        }
        .keyboardShortcut("t", modifiers: [.command, .shift])
    }

    // Replace a built-in menu group
    CommandGroup(replacing: .help) {
        Button("Online Documentation") {
            openDocs()
        }
    }

    // Insert after a built-in menu group
    CommandGroup(after: .sidebar) {
        Button("Toggle Inspector") {
            showInspector.toggle()
        }
        .keyboardShortcut("i", modifiers: [.command, .option])
    }
}
```

### Reading focused state in commands

```swift
struct MyApp: App {
    @FocusedValue(\.selectedDocument) private var selectedDocument

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .commands {
            CommandMenu("Document") {
                Button("Duplicate") {
                    selectedDocument?.duplicate()
                }
                .disabled(selectedDocument == nil)
            }
        }
    }
}

// Define the focused value key
struct SelectedDocumentKey: FocusedValueKey {
    typealias Value = DocumentModel
}

extension FocusedValues {
    var selectedDocument: DocumentModel? {
        get { self[SelectedDocumentKey.self] }
        set { self[SelectedDocumentKey.self] = newValue }
    }
}
```

## Menu Bar Extra Apps

`MenuBarExtra` creates a menu bar icon with a dropdown — either a simple menu or a full SwiftUI window.

### Simple menu-style

```swift
@main
struct StatusBarApp: App {
    var body: some Scene {
        MenuBarExtra("My Utility", systemImage: "gauge.medium") {
            Button("Show Dashboard") {
                openWindow(id: "dashboard")
            }
            .keyboardShortcut("d")

            Divider()

            Button("Quit") {
                NSApplication.shared.terminate(nil)
            }
            .keyboardShortcut("q")
        }
    }
}
```

### Window-style menu bar extra

```swift
@main
struct StatusBarApp: App {
    var body: some Scene {
        MenuBarExtra("My Utility", systemImage: "gauge.medium") {
            VStack(spacing: 12) {
                Text("CPU Usage: 42%")
                    .font(.headline)
                ProgressView(value: 0.42)
                Button("Details...") {
                    openWindow(id: "details")
                }
            }
            .padding()
            .frame(width: 240)
        }
        .menuBarExtraStyle(.window) // renders as a popover-like window
    }
}
```

### Standalone menu bar app (no dock icon)

Set `LSUIElement = YES` in `Info.plist` (or "Application is agent" in Xcode) to hide the dock icon. Combine with `MenuBarExtra` as the only scene:

```swift
@main
struct AgentApp: App {
    var body: some Scene {
        MenuBarExtra("Agent", systemImage: "eye") {
            AgentMenuView()
        }
        .menuBarExtraStyle(.window)
    }
}
```

## Toolbar

### Basic toolbar

```swift
struct ContentView: View {
    @State private var searchText = ""

    var body: some View {
        NavigationSplitView {
            SidebarView()
        } detail: {
            DetailView()
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button(action: addItem) {
                    Label("Add", systemImage: "plus")
                }
            }

            ToolbarItem(placement: .navigation) {
                Button(action: goBack) {
                    Label("Back", systemImage: "chevron.left")
                }
            }
        }
        .searchable(text: $searchText)
    }
}
```

### Toolbar item groups

```swift
.toolbar {
    ToolbarItemGroup(placement: .primaryAction) {
        Button("Bold", systemImage: "bold") { toggleBold() }
        Button("Italic", systemImage: "italic") { toggleItalic() }
        Button("Underline", systemImage: "underline") { toggleUnderline() }
    }
}
```

### Customizable toolbar

```swift
.toolbar(id: "editor-toolbar") {
    ToolbarItem(id: "bold", placement: .automatic) {
        Button("Bold", systemImage: "bold") { toggleBold() }
    }

    ToolbarItem(id: "italic", placement: .automatic) {
        Button("Italic", systemImage: "italic") { toggleItalic() }
    }

    ToolbarItem(id: "font-size", placement: .automatic, showsByDefault: false) {
        FontSizePicker(size: $fontSize)
    }
}
.toolbarRole(.editor)
```

Users can right-click the toolbar to customize which items appear. Items with `showsByDefault: false` are available but hidden initially.

### macOS-specific placements

| Placement | Location |
|---|---|
| `.primaryAction` | Leading area of toolbar (right on macOS) |
| `.secondaryAction` | Overflow menu |
| `.navigation` | Leading edge, near title |
| `.automatic` | System decides |
| `.confirmationAction` | Trailing edge (sheets/dialogs) |
| `.cancellationAction` | Leading edge (sheets/dialogs) |

## Settings / Preferences

### Settings scene

```swift
@main
struct MyApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }

        Settings {
            SettingsView()
        }
    }
}
```

This automatically wires up the standard **App Name > Settings...** menu item (Cmd+,).

### Tabbed preferences

```swift
struct SettingsView: View {
    var body: some View {
        TabView {
            GeneralSettingsView()
                .tabItem {
                    Label("General", systemImage: "gear")
                }

            AppearanceSettingsView()
                .tabItem {
                    Label("Appearance", systemImage: "paintbrush")
                }

            AdvancedSettingsView()
                .tabItem {
                    Label("Advanced", systemImage: "gearshape.2")
                }
        }
        .frame(width: 450)
    }
}
```

### Using @AppStorage for preferences

```swift
struct GeneralSettingsView: View {
    @AppStorage("refreshInterval") private var refreshInterval = 60
    @AppStorage("showNotifications") private var showNotifications = true
    @AppStorage("defaultExportFormat") private var defaultExportFormat = "pdf"

    var body: some View {
        Form {
            Picker("Refresh interval", selection: $refreshInterval) {
                Text("30 seconds").tag(30)
                Text("1 minute").tag(60)
                Text("5 minutes").tag(300)
            }

            Toggle("Show notifications", isOn: $showNotifications)

            Picker("Default export format", selection: $defaultExportFormat) {
                Text("PDF").tag("pdf")
                Text("PNG").tag("png")
                Text("SVG").tag("svg")
            }
        }
        .padding()
        .frame(width: 350)
    }
}
```

`@AppStorage` reads/writes `UserDefaults`. Use it for simple preferences. For complex settings, use `@Observable` models backed by a custom persistence layer.

## AppKit Interop

Use AppKit when SwiftUI lacks a capability: custom `NSTextField` behavior, `NSOutlineView`, `NSSharingServicePicker`, drag-and-drop with file promises, or low-level event handling.

### NSViewRepresentable

```swift
struct AttributedTextView: NSViewRepresentable {
    var attributedString: NSAttributedString

    func makeNSView(context: Context) -> NSTextView {
        let textView = NSTextView()
        textView.isEditable = false
        textView.drawsBackground = false
        textView.textStorage?.setAttributedString(attributedString)
        return textView
    }

    func updateNSView(_ nsView: NSTextView, context: Context) {
        nsView.textStorage?.setAttributedString(attributedString)
    }
}
```

### NSViewControllerRepresentable

```swift
struct WebKitView: NSViewControllerRepresentable {
    let url: URL

    func makeNSViewController(context: Context) -> WebViewController {
        let controller = WebViewController()
        controller.load(url: url)
        return controller
    }

    func updateNSViewController(_ nsViewController: WebViewController, context: Context) {
        nsViewController.load(url: url)
    }
}
```

### NSHostingController — embedding SwiftUI in AppKit

```swift
// When integrating SwiftUI into an existing AppKit app
let hostingController = NSHostingController(rootView: MySwiftUIView())
window.contentViewController = hostingController

// Or as a child view controller
addChild(hostingController)
view.addSubview(hostingController.view)
hostingController.view.translatesAutoresizingMaskIntoConstraints = false
NSLayoutConstraint.activate([
    hostingController.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
    hostingController.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
    hostingController.view.topAnchor.constraint(equalTo: view.topAnchor),
    hostingController.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
])
```

### When to drop to AppKit

| Scenario | Reason |
|---|---|
| Complex `NSOutlineView` trees | SwiftUI `List` with `DisclosureGroup` has limited performance for deep trees |
| Custom text editing (`NSTextView`) | SwiftUI `TextEditor` lacks rich text, custom input, and inline attachments |
| `NSSharingServicePicker` | No SwiftUI equivalent for the native share sheet |
| Status items with custom drawing | `MenuBarExtra` covers most cases, but custom popover positioning needs `NSStatusItem` |
| File promises for drag and drop | SwiftUI drag/drop does not support `NSFilePromiseProvider` |
| Low-level event monitoring | `NSEvent.addGlobalMonitorForEvents` has no SwiftUI equivalent |

### Coordinator pattern for delegates

```swift
struct SearchField: NSViewRepresentable {
    @Binding var text: String

    func makeNSView(context: Context) -> NSSearchField {
        let field = NSSearchField()
        field.delegate = context.coordinator
        return field
    }

    func updateNSView(_ nsView: NSSearchField, context: Context) {
        nsView.stringValue = text
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text)
    }

    class Coordinator: NSObject, NSSearchFieldDelegate {
        var text: Binding<String>

        init(text: Binding<String>) {
            self.text = text
        }

        func controlTextDidChange(_ notification: Notification) {
            guard let field = notification.object as? NSSearchField else { return }
            text.wrappedValue = field.stringValue
        }
    }
}
```

## Sandboxing and Entitlements

macOS apps distributed through the App Store must be sandboxed. Developer ID apps should also be sandboxed when possible.

### App Sandbox basics

Enable in **Signing & Capabilities > App Sandbox**. The sandbox restricts access to:
- File system (app container only by default)
- Network (inbound/outbound)
- Hardware (camera, microphone, USB, Bluetooth)
- System services (printing, Apple Events)

### Common entitlements

| Entitlement | Key | Purpose |
|---|---|---|
| Outbound networking | `com.apple.security.network.client` | HTTP requests, API calls |
| Inbound networking | `com.apple.security.network.server` | Local server, Bonjour |
| User-selected files (read) | `com.apple.security.files.user-selected.read-only` | Open panel access |
| User-selected files (read/write) | `com.apple.security.files.user-selected.read-write` | Save panel access |
| Downloads folder (read/write) | `com.apple.security.files.downloads.read-write` | Direct Downloads access |
| Camera | `com.apple.security.device.camera` | Camera capture |
| Microphone | `com.apple.security.device.audio-input` | Audio recording |

### File access with security-scoped bookmarks

When a user selects a file via an open panel, the sandbox grants temporary access. To persist access across launches, use security-scoped bookmarks:

```swift
// Save a bookmark
func saveBookmark(for url: URL) throws {
    let bookmarkData = try url.bookmarkData(
        options: .withSecurityScope,
        includingResourceValuesForKeys: nil,
        relativeTo: nil
    )
    UserDefaults.standard.set(bookmarkData, forKey: "savedBookmark_\(url.lastPathComponent)")
}

// Restore access from a bookmark
func restoreAccess(key: String) -> URL? {
    guard let data = UserDefaults.standard.data(forKey: key) else { return nil }

    var isStale = false
    guard let url = try? URL(
        resolvingBookmarkData: data,
        options: .withSecurityScope,
        relativeTo: nil,
        bookmarkDataIsStale: &isStale
    ) else { return nil }

    if isStale {
        // Re-save the bookmark
        try? saveBookmark(for: url)
    }

    // MUST call startAccessingSecurityScopedResource before reading
    guard url.startAccessingSecurityScopedResource() else { return nil }
    // Call url.stopAccessingSecurityScopedResource() when done
    return url
}
```

Always call `stopAccessingSecurityScopedResource()` when finished. Failing to do so leaks kernel resources. Use `defer` to guarantee cleanup:

```swift
let url = restoreAccess(key: "savedBookmark_data.json")!
defer { url.stopAccessingSecurityScopedResource() }
let data = try Data(contentsOf: url)
```

## Document-Based Apps

### FileDocument — value-type documents

```swift
struct TextDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.plainText] }

    var text: String

    init(text: String = "") {
        self.text = text
    }

    init(configuration: ReadConfiguration) throws {
        guard let data = configuration.file.regularFileContents,
              let string = String(data: data, encoding: .utf8)
        else {
            throw CocoaError(.fileReadCorruptFile)
        }
        text = string
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        let data = Data(text.utf8)
        return .init(regularFileWithContents: data)
    }
}

@main
struct TextEditorApp: App {
    var body: some Scene {
        DocumentGroup(newDocument: TextDocument()) { file in
            TextEditorView(document: file.$document)
        }
    }
}

struct TextEditorView: View {
    @Binding var document: TextDocument

    var body: some View {
        TextEditor(text: $document.text)
            .padding()
    }
}
```

### ReferenceFileDocument — class-based documents with undo

Use `ReferenceFileDocument` when you need undo support or the document has reference semantics:

```swift
@Observable
class DrawingDocument: ReferenceFileDocument {
    static var readableContentTypes: [UTType] { [.json] }

    var shapes: [Shape] = []

    required init(configuration: ReadConfiguration) throws {
        guard let data = configuration.file.regularFileContents else {
            throw CocoaError(.fileReadCorruptFile)
        }
        shapes = try JSONDecoder().decode([Shape].self, from: data)
    }

    func snapshot(contentType: UTType) throws -> Data {
        try JSONEncoder().encode(shapes)
    }

    func fileWrapper(snapshot: Data, configuration: WriteConfiguration) throws -> FileWrapper {
        .init(regularFileWithContents: snapshot)
    }
}

// Usage with undo
@main
struct DrawingApp: App {
    var body: some Scene {
        DocumentGroup(newDocument: { DrawingDocument() }) { file in
            DrawingCanvas(document: file.document)
        }
    }
}

struct DrawingCanvas: View {
    @ObservedObject var document: DrawingDocument
    @Environment(\.undoManager) var undoManager

    func addShape(_ shape: Shape) {
        let previous = document.shapes
        document.shapes.append(shape)
        undoManager?.registerUndo(withTarget: document) { doc in
            doc.shapes = previous
        }
    }
}
```

### FileDocument vs ReferenceFileDocument

| Aspect | `FileDocument` | `ReferenceFileDocument` |
|---|---|---|
| Semantics | Value type (`struct`) | Reference type (`class`) |
| Undo support | Manual via `@Binding` | Built-in with `UndoManager` |
| Complexity | Simple, small documents | Complex, large documents |
| Thread safety | Copy-on-write | Must handle yourself |

## Drag and Drop (macOS-Specific)

### Basic SwiftUI drag and drop

```swift
struct DragDropView: View {
    @State private var items: [String] = ["Alpha", "Beta", "Gamma"]

    var body: some View {
        HStack {
            List(items, id: \.self) { item in
                Text(item)
                    .draggable(item) // simple string dragging
            }

            DropTargetView()
                .dropDestination(for: String.self) { droppedItems, location in
                    // handle dropped strings
                    processDropped(droppedItems)
                    return true
                }
        }
    }
}
```

### File drops with UTType

```swift
struct FileDropView: View {
    @State private var droppedFiles: [URL] = []

    var body: some View {
        VStack {
            Text("Drop files here")
        }
        .dropDestination(for: URL.self) { urls, location in
            droppedFiles.append(contentsOf: urls)
            return true
        }
    }
}
```

### File promises via AppKit (for deferred file creation)

File promises are needed when the dragged content does not exist on disk yet (e.g., downloading from a server on drop). SwiftUI does not support this natively — use `NSViewRepresentable`:

```swift
class FilePromiseView: NSView, NSDraggingSource, NSFilePromiseProviderDelegate {
    func draggingSession(
        _ session: NSDraggingSession,
        sourceOperationMaskFor context: NSDraggingContext
    ) -> NSDragOperation {
        .copy
    }

    // Provide the file type
    func filePromiseProvider(
        _ provider: NSFilePromiseProvider,
        fileNameForType fileType: String
    ) -> String {
        "exported-data.csv"
    }

    // Write the file when the drop target requests it
    func filePromiseProvider(
        _ provider: NSFilePromiseProvider,
        writePromiseTo url: URL,
        completionHandler: @escaping (Error?) -> Void
    ) {
        do {
            let data = generateCSVData()
            try data.write(to: url)
            completionHandler(nil)
        } catch {
            completionHandler(error)
        }
    }

    func beginDrag() {
        let provider = NSFilePromiseProvider(fileType: UTType.commaSeparatedText.identifier, delegate: self)
        let draggingItem = NSDraggingItem(pasteboardWriter: provider)
        beginDraggingSession(with: [draggingItem], event: currentEvent!, source: self)
    }
}
```

### NSItemProvider for complex drag payloads

```swift
// Creating a drag item with NSItemProvider
let provider = NSItemProvider()
provider.registerDataRepresentation(
    forTypeIdentifier: UTType.json.identifier,
    visibility: .all
) {
    let data = try? JSONEncoder().encode(myModel)
    $0(data, nil)
    return nil
}
```

## Distribution

### Distribution channels

| Channel | Signing | Review | Sandbox Required | Update Mechanism |
|---|---|---|---|---|
| App Store | Apple Distribution cert | Yes | Yes | App Store automatic |
| Developer ID | Developer ID cert | No | Recommended | Sparkle or custom |
| Direct / Ad Hoc | Self-signed or none | No | No | Manual |

### Notarization

All apps distributed outside the App Store must be notarized by Apple to pass Gatekeeper. Notarization verifies the app is free of known malware and was signed with a Developer ID certificate.

```bash
# Build and archive
xcodebuild archive \
    -scheme MyApp \
    -archivePath ./build/MyApp.xcarchive

# Export for Developer ID distribution
xcodebuild -exportArchive \
    -archivePath ./build/MyApp.xcarchive \
    -exportPath ./build/export \
    -exportOptionsPlist ExportOptions.plist

# Submit for notarization
xcrun notarytool submit ./build/export/MyApp.dmg \
    --apple-id "your@email.com" \
    --team-id "TEAM_ID" \
    --password "@keychain:AC_PASSWORD" \
    --wait

# Staple the notarization ticket
xcrun stapler staple ./build/export/MyApp.dmg
```

### DMG creation

```bash
# Create a DMG with a symlink to /Applications
hdiutil create -volname "MyApp" \
    -srcfolder ./build/export/MyApp.app \
    -ov -format UDZO \
    ./build/MyApp.dmg
```

### PKG installer

```bash
# Build a flat package
pkgbuild --component ./build/export/MyApp.app \
    --install-location /Applications \
    ./build/MyApp.pkg

# Sign the package
productsign --sign "Developer ID Installer: Your Name (TEAM_ID)" \
    ./build/MyApp.pkg \
    ./build/MyApp-signed.pkg
```

### Hardened Runtime

Required for notarization. Enable in **Signing & Capabilities > Hardened Runtime**. Common exceptions:

| Exception | When needed |
|---|---|
| Allow Unsigned Executable Memory | JIT compilation |
| Allow DYLD Environment Variables | Plugin loading |
| Disable Library Validation | Loading third-party dylibs |
| Allow debugging | Only for debug builds |

## Differences from iOS

### No UIKit

macOS uses AppKit, not UIKit. Key naming differences:

| iOS (UIKit) | macOS (AppKit) |
|---|---|
| `UIView` | `NSView` |
| `UIViewController` | `NSViewController` |
| `UIWindow` | `NSWindow` |
| `UIApplication` | `NSApplication` |
| `UIColor` | `NSColor` |
| `UIImage` | `NSImage` |
| `UIViewRepresentable` | `NSViewRepresentable` |
| `UIHostingController` | `NSHostingController` |

### Lifecycle differences

- macOS apps can remain running with no windows open — quitting is explicit (Cmd+Q).
- The app delegate has `applicationShouldTerminateAfterLastWindowClosed(_:)` to control this behavior.
- Background execution is unrestricted (no background modes like iOS).
- No concept of app suspension — apps run until quit.

### Menu-driven UX

- Every macOS app is expected to have a menu bar with standard menus (File, Edit, View, Window, Help).
- SwiftUI provides sensible defaults. Customize with `.commands`.
- Keyboard shortcuts are essential — users expect Cmd-based shortcuts for all common actions.

### Multi-window by default

- `WindowGroup` allows multiple instances of the same window. Users expect Cmd+N to open a new window.
- Use `handlesExternalEvents(matching:)` to route URLs or activities to specific windows.
- Each window can have its own toolbar and state.

### Mouse and trackpad

- Right-click context menus via `.contextMenu` (same API as iOS long-press, different trigger).
- Hover effects with `.onHover` and `isHovered` state.
- Mouse-specific gestures: no swipe gestures, but scroll and magnify are available.

```swift
Text("Hover me")
    .onHover { hovering in
        isHovered = hovering
    }
    .foregroundStyle(isHovered ? .primary : .secondary)
    .scaleEffect(isHovered ? 1.05 : 1.0)
    .animation(.easeInOut(duration: 0.15), value: isHovered)
```

### Window chrome and appearance

```swift
// Hide title bar but keep traffic lights
.windowStyle(.hiddenTitleBar)

// Full-size content under title bar (for custom toolbars)
.toolbar {
    ToolbarItem(placement: .principal) {
        Text("Custom Title")
    }
}

// Translucent sidebar material
NavigationSplitView {
    SidebarView()
        .background(.ultraThinMaterial)
} detail: {
    DetailView()
}
```

### Key differences summary

| Aspect | iOS | macOS |
|---|---|---|
| Primary framework | UIKit | AppKit |
| Window model | Single window (mostly) | Multi-window |
| Navigation | Push/modal | Sidebar + detail, windows |
| Input | Touch | Mouse, keyboard, trackpad |
| App lifecycle | Suspend/resume | Runs until quit |
| Menus | Context menus only | Full menu bar |
| Distribution | App Store only | App Store, Developer ID, direct |
| Sandbox | Always | App Store required, otherwise optional |
