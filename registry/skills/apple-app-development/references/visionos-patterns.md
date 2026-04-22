# visionOS Patterns Reference

Patterns and code examples for building spatial computing apps on visionOS 2+ with Swift 6+ and SwiftUI.

## App Structure

visionOS apps use `WindowGroup` for 2D windows, volumetric windows for bounded 3D content, and `ImmersiveSpace` for unbounded 3D experiences.

```swift
import SwiftUI
import RealityKit

@main
struct SpatialApp: App {
    @State private var appModel = AppModel()

    var body: some Scene {
        // Standard 2D window
        WindowGroup {
            ContentView()
                .environment(appModel)
        }

        // Volumetric window — bounded 3D content
        WindowGroup(id: "volumetric-viewer") {
            VolumetricView()
                .environment(appModel)
        }
        .windowStyle(.volumetric)
        .defaultSize(width: 0.5, height: 0.5, depth: 0.5, in: .meters)

        // Immersive space — unbounded 3D
        ImmersiveSpace(id: "immersive-scene") {
            ImmersiveView()
                .environment(appModel)
        }
        .immersionStyle(selection: $appModel.immersionStyle, in: .mixed, .full, .progressive)
    }
}
```

### Immersion Styles

| Style | Behavior |
|---|---|
| `.mixed` | 3D content overlays passthrough (default for shared space) |
| `.full` | Passthrough hidden, app controls entire visual field |
| `.progressive` | Dial-controlled blend between mixed and full |
| `.automatic` | System decides based on context |

```swift
@Observable
class AppModel {
    var immersionStyle: ImmersionStyle = .mixed
}
```

## RealityKit Fundamentals

`RealityView` is the bridge between SwiftUI and RealityKit. It manages an entity hierarchy inside a SwiftUI view.

### Basic RealityView

```swift
struct ModelViewer: View {
    var body: some View {
        RealityView { content in
            // Called once to set up the scene
            let entity = ModelEntity(
                mesh: .generateSphere(radius: 0.1),
                materials: [SimpleMaterial(color: .blue, isMetallic: true)]
            )
            entity.position = [0, 0.1, 0]
            entity.components.set(InputTargetComponent())
            entity.components.set(CollisionComponent(
                shapes: [.generateSphere(radius: 0.1)]
            ))
            content.add(entity)
        } update: { content in
            // Called when SwiftUI state changes — update entities here
        }
    }
}
```

### Loading USDZ Models

```swift
struct USDZViewer: View {
    var body: some View {
        RealityView { content in
            do {
                let entity = try await Entity(named: "robot", in: .main)
                entity.scale = [0.5, 0.5, 0.5]
                entity.position = [0, 0, -1]
                content.add(entity)
            } catch {
                print("Failed to load model: \(error)")
            }
        }
    }
}
```

### Entity-Component-System (ECS)

Entities are containers. Components hold data. Systems process entities that match a component query.

```swift
// Define a custom component
struct RotationComponent: Component {
    var speed: Float = 1.0
    var axis: SIMD3<Float> = [0, 1, 0]
}

// Define a system that processes entities with that component
struct RotationSystem: System {
    static let query = EntityQuery(where: .has(RotationComponent.self))

    init(scene: RealityKit.Scene) {}

    func update(context: SceneUpdateContext) {
        for entity in context.entities(matching: Self.query, updatingSystemWhen: .rendering) {
            guard let rotation = entity.components[RotationComponent.self] else { continue }
            let angle = rotation.speed * Float(context.deltaTime)
            entity.transform.rotation *= simd_quatf(angle: angle, axis: rotation.axis)
        }
    }
}

// Register the system and attach the component
struct RotatingModelView: View {
    var body: some View {
        RealityView { content in
            RotationSystem.registerSystem()
            RotationComponent.registerComponent()

            let sphere = ModelEntity(
                mesh: .generateSphere(radius: 0.1),
                materials: [SimpleMaterial(color: .green, isMetallic: false)]
            )
            sphere.components.set(RotationComponent(speed: 0.5))
            content.add(sphere)
        }
    }
}
```

## Volumes

Volumes display 3D content in a bounded window that users can reposition. Content is clipped to the volume boundary.

```swift
WindowGroup(id: "globe") {
    GlobeView()
}
.windowStyle(.volumetric)
.defaultSize(width: 0.4, height: 0.4, depth: 0.4, in: .meters)
.windowResizability(.contentSize)
```

### Volume World Alignment

```swift
WindowGroup(id: "table-scene") {
    TableTopView()
}
.windowStyle(.volumetric)
.defaultWorldAlignment(.gravityAligned) // content stays upright relative to gravity
```

| Alignment | Use Case |
|---|---|
| `.gravityAligned` | Objects that should stay upright (globes, figurines) |
| `.camera` | HUD-style content facing the user |

### Sizing and Positioning Content Inside a Volume

```swift
struct GlobeView: View {
    var body: some View {
        RealityView { content in
            let globe = try? await Entity(named: "earth")
            globe?.scale = SIMD3(repeating: 0.3)
            // Center in volume — origin is at the volume center
            globe?.position = .zero
            if let globe { content.add(globe) }
        }
    }
}
```

Rules:
- Keep models within the declared volume size; content outside is clipped.
- Use `.defaultSize(width:height:depth:in:)` with `.meters` for predictable sizing.
- Volumes exist in the shared space by default — they coexist with other apps.

## Immersive Spaces

Immersive spaces provide an unbounded 3D canvas. Only one immersive space can be open at a time across the system.

### Opening and Dismissing

```swift
struct ContentView: View {
    @Environment(\.openImmersiveSpace) private var openImmersiveSpace
    @Environment(\.dismissImmersiveSpace) private var dismissImmersiveSpace
    @State private var isImmersive = false

    var body: some View {
        VStack {
            Toggle("Enter Immersive Mode", isOn: $isImmersive)
        }
        .onChange(of: isImmersive) { _, newValue in
            Task {
                if newValue {
                    let result = await openImmersiveSpace(id: "immersive-scene")
                    switch result {
                    case .opened:
                        break
                    case .userCancelled, .error:
                        isImmersive = false
                    @unknown default:
                        isImmersive = false
                    }
                } else {
                    await dismissImmersiveSpace()
                }
            }
        }
    }
}
```

### Passthrough and Full Immersion

```swift
// Mixed — 3D content composited over real world (passthrough visible)
ImmersiveSpace(id: "mixed-scene") {
    MixedImmersiveView()
}
.immersionStyle(selection: .constant(.mixed), in: .mixed)

// Full — passthrough hidden, complete environment control
ImmersiveSpace(id: "full-scene") {
    FullImmersiveView()
}
.immersionStyle(selection: .constant(.full), in: .full)
```

Rules:
- Always handle the `openImmersiveSpace` result — the user can cancel or the system can deny.
- Use `.mixed` for AR-style overlays. Use `.full` for cinematic or gaming experiences.
- Dismiss the immersive space when the user navigates away or the app goes to background.

## Spatial Gestures

visionOS gestures work on entities that have both `InputTargetComponent` and `CollisionComponent`.

### Making an Entity Interactive

```swift
func makeInteractive(_ entity: Entity, shape: ShapeResource) {
    entity.components.set(InputTargetComponent())
    entity.components.set(CollisionComponent(shapes: [shape]))
    // Optional: enable hover effect
    entity.components.set(HoverEffectComponent())
}
```

### SpatialTapGesture

```swift
struct TappableModelView: View {
    @State private var tapped = false

    var body: some View {
        RealityView { content in
            let box = ModelEntity(
                mesh: .generateBox(size: 0.2),
                materials: [SimpleMaterial(color: .orange, isMetallic: false)]
            )
            box.name = "myBox"
            makeInteractive(box, shape: .generateBox(size: [0.2, 0.2, 0.2]))
            content.add(box)
        }
        .gesture(
            SpatialTapGesture()
                .targetedToAnyEntity()
                .onEnded { value in
                    let tappedEntity = value.entity
                    print("Tapped: \(tappedEntity.name)")
                    tapped.toggle()
                }
        )
    }
}
```

### DragGesture in 3D

```swift
RealityView { content in
    // ... entity setup with InputTargetComponent and CollisionComponent
}
.gesture(
    DragGesture()
        .targetedToAnyEntity()
        .onChanged { value in
            let entity = value.entity
            // convert2D drag to 3D translation
            entity.position = value.convert(value.location3D, from: .local, to: .scene)
        }
)
```

### RotateGesture3D and MagnifyGesture

```swift
struct ManipulableModelView: View {
    @State private var rotation: Rotation3D = .identity
    @State private var scale: Double = 1.0

    var body: some View {
        RealityView { content in
            // ... setup entity
        }
        .gesture(
            RotateGesture3D()
                .targetedToAnyEntity()
                .onChanged { value in
                    rotation = value.rotation
                }
        )
        .gesture(
            MagnifyGesture()
                .targetedToAnyEntity()
                .onChanged { value in
                    scale = value.magnification
                }
        )
    }
}
```

### Combining Gestures

```swift
.gesture(
    DragGesture()
        .targetedToAnyEntity()
        .simultaneously(with:
            RotateGesture3D()
                .targetedToAnyEntity()
        )
        .simultaneously(with:
            MagnifyGesture()
                .targetedToAnyEntity()
        )
)
```

Rules:
- Every gestured entity needs `InputTargetComponent` + `CollisionComponent`.
- Use `.targetedToAnyEntity()` to receive the entity reference in the gesture value.
- Use `.targetedToEntity(entity)` when you need to restrict gesture targets.

## Ornaments

Ornaments attach supplementary UI (controls, labels) to the edge of a window.

```swift
struct PlayerView: View {
    @State private var isPlaying = false

    var body: some View {
        VolumetricContentView()
            .ornament(
                visibility: .visible,
                attachmentAnchor: .scene(.bottom)
            ) {
                HStack(spacing: 20) {
                    Button(action: { /* skip back */ }) {
                        Image(systemName: "backward.fill")
                    }
                    Button(action: { isPlaying.toggle() }) {
                        Image(systemName: isPlaying ? "pause.fill" : "play.fill")
                    }
                    Button(action: { /* skip forward */ }) {
                        Image(systemName: "forward.fill")
                    }
                }
                .padding()
                .glassBackgroundEffect()
            }
    }
}
```

### Ornament Positioning

| Anchor | Position |
|---|---|
| `.scene(.bottom)` | Below the window |
| `.scene(.top)` | Above the window |
| `.scene(.leading)` | Left edge |
| `.scene(.trailing)` | Right edge |

Rules:
- Use ornaments for controls related to the window content (transport controls, toolbars).
- Apply `.glassBackgroundEffect()` for the standard visionOS glass look.
- Keep ornaments small — they should not dominate the window.

## Eye and Hand Tracking

### ARKit Hand Tracking

Hand tracking requires the `NSHandTrackingUsageDescription` key in Info.plist and a full immersive space.

```swift
import ARKit

@MainActor
class HandTrackingManager {
    private let session = ARKitSession()
    private let handTracking = HandTrackingProvider()

    func start() async throws {
        guard HandTrackingProvider.isSupported else {
            print("Hand tracking not supported")
            return
        }
        try await session.run([handTracking])
    }

    func processUpdates() async {
        for await update in handTracking.anchorUpdates {
            let anchor = update.anchor
            guard anchor.isTracked else { continue }

            // Access specific joints
            if let indexTip = anchor.handSkeleton?.joint(.indexFingerTip),
               indexTip.isTracked {
                let position = anchor.originFromAnchorTransform
                    * indexTip.anchorFromJointTransform
                // Use position for interaction
            }
        }
    }
}
```

### Pinch Detection (Custom)

```swift
func detectPinch(hand: HandAnchor) -> Bool {
    guard let skeleton = hand.handSkeleton,
          skeleton.joint(.thumbTip).isTracked,
          skeleton.joint(.indexFingerTip).isTracked else { return false }

    let thumbTip = skeleton.joint(.thumbTip).anchorFromJointTransform.columns.3
    let indexTip = skeleton.joint(.indexFingerTip).anchorFromJointTransform.columns.3

    let distance = simd_distance(
        SIMD3(thumbTip.x, thumbTip.y, thumbTip.z),
        SIMD3(indexTip.x, indexTip.y, indexTip.z)
    )
    return distance < 0.02 // 2cm threshold
}
```

### Gaze-Based Interaction

The system provides gaze targeting automatically — entities with `InputTargetComponent` and `CollisionComponent` receive hover and tap events from the user's gaze + pinch. No explicit eye-tracking API is needed for standard interactions.

For custom gaze data (requires entitlement):

```swift
import ARKit

let worldTracking = WorldTrackingProvider()
// Device anchor provides head pose; eye gaze requires
// com.apple.developer.arkit.eye-tracking-provider entitlement
```

### Accessibility Considerations

- Always provide `InputTargetComponent` so standard gaze+pinch interaction works.
- Supplement hand gestures with alternative controls (buttons, menus) for users who cannot use hand tracking.
- Add accessibility labels to interactive entities via SwiftUI overlays or ornaments.

## Shared Spaces vs Full Spaces

### Shared Space (Default)

All apps start in the shared space. Multiple apps coexist side by side.

```swift
// Windows and volumes live in shared space by default
WindowGroup { ContentView() }

WindowGroup(id: "model-viewer") { ModelView() }
    .windowStyle(.volumetric)
```

Constraints in shared space:
- No world anchoring; windows float in front of the user.
- Limited entity placement — content is inside windows/volumes only.
- Cannot use `WorldTrackingProvider` or `PlaneDetectionProvider`.
- Other apps remain visible.

### Full Space

When you open an `ImmersiveSpace`, the app transitions to Full Space. Other apps are hidden.

```swift
ImmersiveSpace(id: "full-experience") {
    FullExperienceView()
}
.immersionStyle(selection: .constant(.full), in: .full)
```

Full Space unlocks:
- World anchoring and plane detection (ARKit).
- Unbounded entity placement anywhere in the user's environment.
- Hand tracking and scene understanding.

### When to Use Each

| Scenario | Space Type |
|---|---|
| Utility app, dashboard, media player | Shared (window / volume) |
| Interactive 3D model viewer | Shared (volume) |
| AR furniture placement | Full Space, mixed immersion |
| VR game, cinematic experience | Full Space, full immersion |
| Guided meditation with environment | Full Space, progressive immersion |

### App Lifecycle in Shared Space

```swift
struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Text("Hello, visionOS")
            .onChange(of: scenePhase) { _, newPhase in
                switch newPhase {
                case .active:
                    // Window is visible and interactive
                    break
                case .inactive:
                    // Window is visible but not interactive (e.g., system overlay)
                    break
                case .background:
                    // Window is not visible — reduce work
                    break
                @unknown default:
                    break
                }
            }
    }
}
```

## 3D Text and Materials

### 3D Extruded Text

```swift
func createTextEntity(_ string: String) -> ModelEntity {
    let mesh = MeshResource.generateText(
        string,
        extrusionDepth: 0.02,
        font: .systemFont(ofSize: 0.1, weight: .bold),
        containerFrame: .zero,
        alignment: .center,
        lineBreakMode: .byWordWrapping
    )
    let material = SimpleMaterial(color: .white, isMetallic: false)
    let entity = ModelEntity(mesh: mesh, materials: [material])
    // Center the text
    let bounds = entity.visualBounds(relativeTo: nil)
    entity.position.x = -bounds.center.x
    return entity
}
```

### SimpleMaterial

```swift
// Solid color
let redMetal = SimpleMaterial(color: .red, isMetallic: true)

// With roughness control
var material = SimpleMaterial()
material.color = .init(tint: .blue)
material.roughness = .float(0.2) // 0 = mirror, 1 = matte
material.metallic = .float(0.9)
```

### ShaderGraphMaterial (from Reality Composer Pro)

```swift
// Load a custom material authored in Reality Composer Pro
func loadCustomMaterial() async throws -> ShaderGraphMaterial {
    var material = try await ShaderGraphMaterial(
        named: "/Root/CustomMaterial",
        from: "Scene.usda",
        in: .main
    )
    // Set parameter values at runtime
    try material.setParameter(name: "BaseColor", value: .color(.cyan))
    try material.setParameter(name: "Opacity", value: .float(0.8))
    return material
}
```

### Custom MeshResource

```swift
// Programmatic mesh generation
func createCustomMesh() throws -> MeshResource {
    var descriptor = MeshDescriptor(name: "customPlane")
    descriptor.positions = MeshBuffer([
        SIMD3<Float>(-0.5, 0, -0.5),
        SIMD3<Float>( 0.5, 0, -0.5),
        SIMD3<Float>( 0.5, 0,  0.5),
        SIMD3<Float>(-0.5, 0,  0.5),
    ])
    descriptor.normals = MeshBuffer([
        SIMD3<Float>(0, 1, 0),
        SIMD3<Float>(0, 1, 0),
        SIMD3<Float>(0, 1, 0),
        SIMD3<Float>(0, 1, 0),
    ])
    descriptor.primitives = .triangles([0, 1, 2, 0, 2, 3])
    return try MeshResource.generate(from: [descriptor])
}
```

## Porting from iOS

### Window Sizing

iOS apps run in a fixed-size window on visionOS. Adapt by declaring a default window size:

```swift
WindowGroup {
    ContentView()
}
.defaultSize(width: 1280, height: 720) // points, not pixels
```

### Depth and Hover Effects

Add depth cues and hover effects to make flat UI feel spatial:

```swift
struct AdaptedCardView: View {
    var body: some View {
        VStack {
            Image("product")
                .resizable()
                .scaledToFit()
            Text("Product Name")
                .font(.headline)
        }
        .padding()
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .hoverEffect(.highlight) // standard lift + glow on gaze
        .frame(depth: 20)        // push content forward in z-axis
    }
}
```

### Key Porting Considerations

| iOS Pattern | visionOS Adaptation |
|---|---|
| `UINavigationController` | `NavigationStack` (already SwiftUI — works as-is) |
| Tab bar (`UITabBarController`) | `TabView` with ornament-style tab bar |
| Flat buttons | Add `.hoverEffect()` for gaze feedback |
| Scroll views | Work as-is; consider adding depth to items |
| Camera/ARKit (iOS) | Rewrite with visionOS ARKit providers |
| Touch gestures | Map to spatial gestures (tap = gaze+pinch) |
| `UIScreen.main.bounds` | Use `GeometryReader3D` or window default size |

### Gradual Adoption Strategy

```swift
@main
struct MyPortedApp: App {
    var body: some Scene {
        // Phase 1: Existing iOS UI in a window
        WindowGroup {
            ExistingRootView()
        }

        // Phase 2: Add a volumetric viewer for 3D content
        WindowGroup(id: "3d-preview") {
            ModelPreviewView()
        }
        .windowStyle(.volumetric)
        .defaultSize(width: 0.3, height: 0.3, depth: 0.3, in: .meters)

        // Phase 3: Full immersive experience
        ImmersiveSpace(id: "immersive") {
            ImmersiveProductView()
        }
    }
}
```

Rules:
- Start with your existing SwiftUI app running as a window.
- Add `.hoverEffect()` throughout for gaze feedback.
- Introduce volumes and immersive spaces incrementally.
- Replace any `UIScreen`-based layout with `GeometryReader` / `GeometryReader3D`.

## Accessibility in Spatial Computing

### VoiceOver in visionOS

VoiceOver works spatially — it describes objects in 3D space and supports gaze-based navigation.

```swift
struct AccessibleModelView: View {
    var body: some View {
        RealityView { content in
            let entity = try? await Entity(named: "trophy")
            if let entity {
                entity.components.set(InputTargetComponent())
                entity.components.set(CollisionComponent(
                    shapes: [.generateBox(size: [0.2, 0.3, 0.2])]
                ))
                content.add(entity)
            }
        }
        .accessibilityLabel("Gold trophy")
        .accessibilityHint("Double tap to view details")
        .accessibilityAddTraits(.isButton)
    }
}
```

### Pointer Accessibility

Users who cannot perform gaze+pinch can use Pointer Control (head tracking, wrist-based pointer, or assistive devices):

```swift
// Ensure all interactive elements are reachable via standard controls
Button("View in 3D") {
    // action
}
.accessibilityLabel("View product in 3D space")
```

### Alternative Interaction Modes

| Mode | How It Works | Design Consideration |
|---|---|---|
| Gaze + Pinch | Default; look at target, pinch to select | Ensure targets are at least 60pt equivalent |
| Pointer Control | Head or wrist pointer replaces gaze | All targets must have `CollisionComponent` |
| Switch Control | External switch triggers actions | Ensure linear navigation order makes sense |
| Voice Control | Voice commands for actions | Provide clear `accessibilityLabel` values |
| Keyboard | Bluetooth keyboard navigation | Support focus system in SwiftUI views |

### Best Practices

- Provide accessibility labels for all interactive 3D entities.
- Never rely solely on spatial audio or visual cues — pair them with text or haptic alternatives.
- Test with VoiceOver enabled in the visionOS simulator.
- Use `accessibilityZoomAction` to provide alternative zoom controls for users who cannot perform magnify gestures.
- Ensure custom gestures have button/menu alternatives.

## Performance

### Render Budget

visionOS targets 90 fps per eye (stereo rendering). The render budget is approximately 11ms per frame.

| Budget Area | Guideline |
|---|---|
| Triangle count | Aim for < 500K total visible triangles |
| Draw calls | Minimize — batch materials, use instancing |
| Texture memory | Compress textures (ASTC), use mipmaps |
| Shader complexity | Prefer `SimpleMaterial` or optimized `ShaderGraphMaterial` |
| Physics | Limit dynamic rigid bodies; use static colliders where possible |

### Entity Level of Detail (LOD)

Use multiple mesh resolutions and switch based on distance or visibility:

```swift
struct LODComponent: Component {
    let highDetail: MeshResource
    let lowDetail: MeshResource
    let switchDistance: Float
}

struct LODSystem: System {
    static let query = EntityQuery(where: .has(LODComponent.self))

    // On visionOS, use WorldTrackingProvider.deviceAnchor for user position.
    // PerspectiveCameraComponent is for non-visionOS RealityKit (iOS/macOS).
    private var worldTracking: WorldTrackingProvider?

    init(scene: RealityKit.Scene) {
        // WorldTrackingProvider should be started in your ImmersiveSpace setup
        // and passed to this system or stored in a shared location.
    }

    func update(context: SceneUpdateContext) {
        guard let deviceAnchor = worldTracking?.queryDeviceAnchor(atTimestamp: CACurrentMediaTime()) else { return }
        let headPosition = deviceAnchor.originFromAnchorTransform.columns.3

        for entity in context.entities(matching: Self.query, updatingSystemWhen: .rendering) {
            guard let lod = entity.components[LODComponent.self],
                  var model = entity.components[ModelComponent.self] else { continue }

            let distance = simd_distance(
                entity.position(relativeTo: nil),
                SIMD3(headPosition.x, headPosition.y, headPosition.z)
            )
            let targetMesh = distance > lod.switchDistance ? lod.lowDetail : lod.highDetail
            if model.mesh !== targetMesh {
                model.mesh = targetMesh
                entity.components.set(model)
            }
        }
    }
}
```

### Optimizing 3D Assets

- **Decimate meshes** — use Reality Composer Pro or Blender to reduce polygon counts.
- **Merge meshes** that share the same material to reduce draw calls.
- **Use USDZ** as the delivery format; it supports mesh compression.
- **Compress textures** — ASTC format, power-of-two dimensions, enable mipmaps.
- **Avoid overdraw** — minimize overlapping transparent surfaces.

### Profiling Tools

| Tool | Purpose |
|---|---|
| RealityKit Trace (Instruments) | Frame time, render stats, entity counts |
| GPU Report (Xcode) | Shader compilation, GPU utilization |
| Reality Composer Pro Statistics | Asset triangle/vertex counts before loading |
| `RealityView` debug options | Wireframe, bounding boxes during development |

### General Rules

- Profile on device (Apple Vision Pro), not just the simulator.
- Keep the entity hierarchy shallow — deep nesting increases traversal cost.
- Disable components (physics, collision) on entities that do not need them.
- Use `async` loading for models to avoid blocking the main actor during scene setup.
- Prefer static meshes over animated ones when motion is not required.


## visionOS 2+ Features

### Object Tracking (visionOS 2)

Track real-world objects using `ObjectTrackingProvider`:

```swift
let session = ARKitSession()
let objectTracking = ObjectTrackingProvider(
    referenceObjects: ReferenceObject.loadReferenceObjects(inGroupNamed: "TrackedObjects")
)

try await session.run([objectTracking])

for await update in objectTracking.anchorUpdates {
    switch update.event {
    case .added, .updated:
        let anchor = update.anchor
        // Position virtual content relative to tracked object
        entity.transform = Transform(matrix: anchor.originFromAnchorTransform)
    case .removed:
        break
    }
}
```

### TabletopKit (visionOS 2)

Framework for building tabletop experiences (board games, collaborative tools). Manages player seating, game pieces, and table surface interactions.

### visionOS 26 Features

- **ManipulationComponent** — Built-in component for object manipulation, replacing much custom gesture code. Add to entities for drag, rotate, and scale behaviors.
- **Persistence APIs** — Content can be locked to physical surfaces and persist across app sessions using spatial anchors.
- **ImagePresentationComponent** — New component for displaying 2D, spatial photos, and spatial scenes in RealityKit.
- **Unified Coordinate Conversion** — Simplifies moving between SwiftUI, RealityKit, and ARKit coordinate spaces.
- **WidgetKit on visionOS** — Widgets are now available on visionOS 26.
- **Spatial accessories** — Support for PlayStation VR2 Sense controllers and Logitech Muse.
