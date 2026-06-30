# Android Background Work Reference

> Covers Foreground Services, background execution limits, and AlarmManager. For coroutine-based
> background work (WorkManager, viewModelScope, lifecycleScope), see `concurrency.md`.

>[toc]


## Foreground Services

Use a Foreground Service for long-running, user-perceptible tasks that must continue even if the user navigates away (e.g., music playback, navigation, active location tracking).

### When to use

| Scenario | Solution |
|---|---|
| Deferred, can survive process restart | WorkManager |
| User-initiated, must complete soon | WorkManager (expedited) |
| Long-running, user-perceptible | Foreground Service |
| Exact timing required | AlarmManager |

### Foreground Service types (API 34+)

As of API 34, you must declare a specific foreground service type in `AndroidManifest.xml` and the corresponding permission:

```xml
<manifest>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION" />

    <service
        android:name=".TrackingService"
        android:foregroundServiceType="location"
        android:exported="false" />
</manifest>
```

Available types: `camera`, `connectedDevice`, `dataSync`, `health`, `location`, `mediaPlayback`, `mediaProcessing`, `mediaProjection`, `microphone`, `phoneCall`, `remoteMessaging`, `shortService`, `specialUse`, `systemExempted`.

### Implementation

```kotlin
class TrackingService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = createNotification()

        // Must call startForeground within 5 seconds of service start
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            notification,
            ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION,
        )

        scope.launch {
            locationProvider.locationUpdates().collect { location ->
                updateNotification(location)
                saveLocation(location)
            }
        }

        return START_STICKY
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotification(): Notification {
        // NotificationChannel is required on API 26+
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Location Tracking",
            NotificationManager.IMPORTANCE_LOW,
        )
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Tracking location")
            .setSmallIcon(R.drawable.ic_location)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val NOTIFICATION_ID = 1
        private const val CHANNEL_ID = "location_tracking"
    }
}
```

### Starting and stopping

```kotlin
// Starting from Activity, Fragment, or other component
val intent = Intent(context, TrackingService::class.java)
ContextCompat.startForegroundService(context, intent)

// Stopping from outside
context.stopService(Intent(context, TrackingService::class.java))

// Stopping from within the service
stopForeground(STOP_FOREGROUND_REMOVE)
stopSelf()
```

### Restrictions

**API 31+ (Android 12):** Apps cannot start foreground services from the background except in specific exemptions (high-priority FCM message, exact alarm callback, `SYSTEM_ALERT_WINDOW` permission, etc.). Use WorkManager with `setExpedited()` for background-initiated urgent work.

**API 35+ (Android 15):** The `dataSync` and `mediaProcessing` foreground service types have a 6-hour time limit. For longer sync tasks, use WorkManager or the `mediaProcessing` type where applicable. The `shortService` type has a 3-minute limit.


## Background Limits

Android progressively restricts background work to preserve battery. Understanding these limits is essential for reliable app behavior.

### Doze mode (API 23+)

When the device is stationary, unplugged, and screen-off for a period, the system enters Doze mode:
- Network access is suspended.
- Wake locks are ignored.
- `AlarmManager` alarms (inexact) are deferred to maintenance windows.
- `JobScheduler` / `WorkManager` jobs are deferred.
- `SyncAdapter` runs are deferred.

Maintenance windows periodically open to allow deferred work to execute. The intervals between windows increase over time (minutes to hours).

**What still works in Doze:**
- `setExactAndAllowWhileIdle()` alarms (limited to approximately 1 per 9 minutes)
- FCM high-priority messages (grant a short execution window)
- Foreground Services already running

### App Standby Buckets (API 28+)

The system categorizes apps by recent usage into buckets that determine job and alarm frequency:

| Bucket | Criteria | Job frequency |
|---|---|---|
| Active | Currently in use | No restrictions |
| Working Set | Used regularly | Deferred up to 2 hours |
| Frequent | Used often, not daily | Deferred up to 8 hours |
| Rare | Rarely used | Deferred up to 24 hours |
| Restricted (API 31+) | Minimal usage + high battery drain | 1 job per day, no expedited jobs, no alarms |

### Background execution limits (API 26+)

- Apps in the background cannot start services freely. Use `startForegroundService()` and call `startForeground()` within 5 seconds, or use WorkManager.
- Background location access requires `ACCESS_BACKGROUND_LOCATION` permission (API 29+) and Play Store policy approval.
- Implicit broadcast receivers registered in the manifest are restricted. Register them dynamically at runtime or use explicit broadcasts.

### Practical design implications

- Design for eventual execution, not exact timing, for all deferrable work.
- Use WorkManager as the default for background processing — it handles Doze, Standby, and restart automatically.
- Use FCM high-priority messages for time-sensitive server-driven events.
- Test your app's behavior across buckets using `adb shell am set-standby-bucket <package> <bucket>`.
- Recent platform versions tighten restrictions further: jobs started alongside a foreground service are no longer exempt from runtime quotas. Design background work to stay within quota limits even when a foreground service is running.


## AlarmManager

Use AlarmManager only when you need execution at an exact time regardless of app state (e.g., calendar reminders, medication alerts). For most other background work, prefer WorkManager.

### Exact vs inexact alarms

```kotlin
val alarmManager = context.getSystemService<AlarmManager>()

// Inexact — system batches with other alarms to save battery
alarmManager.set(
    AlarmManager.RTC_WAKEUP,
    triggerTimeMillis,
    pendingIntent,
)

// Inexact but survives Doze
alarmManager.setAndAllowWhileIdle(
    AlarmManager.RTC_WAKEUP,
    triggerTimeMillis,
    pendingIntent,
)

// Exact — requires SCHEDULE_EXACT_ALARM permission (API 31+)
if (alarmManager.canScheduleExactAlarms()) {
    alarmManager.setExactAndAllowWhileIdle(
        AlarmManager.RTC_WAKEUP,
        triggerTimeMillis,
        pendingIntent,
    )
}
```

### Permissions (API 31+)

```xml
<!-- For clock, timer, and calendar apps — auto-granted, Play Store restricted -->
<uses-permission android:name="android.permission.USE_EXACT_ALARM" />

<!-- For other exact alarms — user must grant in Settings -->
<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" />
```

```kotlin
// Check and request exact alarm permission
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
    if (!alarmManager.canScheduleExactAlarms()) {
        startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM))
    }
}
```

### Alarm receiver pattern

Keep work minimal in the receiver (10-second execution limit). For longer work, delegate to WorkManager:

```kotlin
class ReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val reminderId = intent.getLongExtra("reminderId", -1)

        // Delegate longer work to WorkManager
        val workRequest = OneTimeWorkRequestBuilder<ReminderNotificationWorker>()
            .setInputData(workDataOf("reminderId" to reminderId))
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .build()
        WorkManager.getInstance(context).enqueue(workRequest)
    }
}
```

### Alarms vs WorkManager

| Criteria | AlarmManager | WorkManager |
|---|---|---|
| Exact timing | Yes | No (approximate) |
| Survives reboot | Yes (with `RECEIVE_BOOT_COMPLETED`) | Yes (built-in) |
| Constraints (network, battery) | No | Yes |
| Retry / chaining | Manual | Built-in |
| Battery-friendly | No | Yes |
| Guaranteed execution | Time-based | Condition-based |

Rules:
- Prefer inexact alarms unless the app genuinely needs exact timing (alarms, reminders, calendar).
- On API 31+, exact alarms require permission and user consent.
- Alarms are cleared on device reboot — re-register in a `BOOT_COMPLETED` receiver if needed.
- Combine AlarmManager (time trigger) with WorkManager (execution) for robust patterns.
