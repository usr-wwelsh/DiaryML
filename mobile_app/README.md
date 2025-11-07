# DiaryML Mobile App

A Flutter-based mobile companion app for DiaryML - your private AI diary.

## Features

✨ **Full-Featured Mobile Experience**
- 📝 Quick journal entries with voice input
- 📷 Camera integration for image entries
- 🔄 Error-resistant bidirectional sync
- 📊 Insights dashboard with mood tracking
- 🌙 Beautiful dark theme UI
- 💾 Offline-first with local SQLite cache
- 🔐 JWT authentication (30-day tokens)
- 🔒 Secure local storage with encryption

## Prerequisites

- Flutter SDK 3.0+
- Android Studio or VS Code
- Android SDK (API 21+)
- DiaryML backend server running

## Installation

### 1. Install Flutter

```bash
# Download Flutter
git clone https://github.com/flutter/flutter.git -b stable
export PATH="$PATH:`pwd`/flutter/bin"

# Verify installation
flutter doctor
```

### 2. Install Dependencies

```bash
cd mobile_app
flutter pub get
```

### 3. Configure Server URL

Edit `lib/services/api_client.dart` and update the default server URL:

```dart
static const String defaultBaseUrl = 'http://YOUR_IP:8000/api';
```

Or configure it in the app's login screen under "Server Settings".

## Building

### Development Build (Debug)

```bash
flutter build apk --debug
```

Output: `build/app/outputs/flutter-apk/app-debug.apk`

### Production Build (Release)

```bash
flutter build apk --release
```

Output: `build/app/outputs/flutter-apk/app-release.apk`

### Build for Specific ABI

```bash
# ARM64 only (smaller size, most modern devices)
flutter build apk --release --target-platform android-arm64

# Multiple ABIs (larger size, better compatibility)
flutter build apk --release --split-per-abi
```

## Installation on Device

### Via ADB

```bash
# Install debug build
adb install build/app/outputs/flutter-apk/app-debug.apk

# Install release build
adb install build/app/outputs/flutter-apk/app-release.apk
```

### Via File Transfer

1. Copy APK to phone
2. Enable "Install from Unknown Sources" in Android settings
3. Tap the APK file to install

## Permissions

The app requests the following permissions:

- **Internet** - Sync with DiaryML server
- **Microphone** - Voice input for entries
- **Camera** - Take photos for entries
- **Storage** - Save images and local database
- **Network State** - Check connectivity before sync

All permissions are optional except Internet.

## Architecture

```
lib/
├── models/          # Data models (DiaryEntry, etc.)
├── services/        # Backend services
│   ├── api_client.dart      # FastAPI communication
│   ├── local_database.dart  # SQLite offline storage
│   └── sync_service.dart    # Error-resistant sync
├── screens/         # UI screens
│   ├── login_screen.dart
│   ├── home_screen.dart
│   ├── entry_edit_screen.dart
│   └── insights_screen.dart
└── main.dart        # App entry point
```

## Sync System

### How It Works

1. **Offline Queue**: Entries saved locally first
2. **Background Sync**: Auto-sync every 15 minutes
3. **Conflict Resolution**: Server-wins strategy
4. **Retry Logic**: 3 attempts with exponential backoff
5. **Error Handling**: Graceful degradation, never lose data

### Sync Triggers

- App startup
- Manual refresh (pull down or sync button)
- After creating new entry
- Periodic background sync (every 15 min)

## Development

### Run in Debug Mode

```bash
flutter run
```

### Hot Reload

Press `r` in terminal or use IDE hot reload button

### View Logs

```bash
flutter logs
```

### Run Tests

```bash
flutter test
```

## Troubleshooting

### "Connection refused"

- Check server URL in settings
- Ensure backend server is running
- Verify you're on the same network (or use ngrok for external access)

### "Authentication expired"

- Login again to get new JWT token
- Tokens expire after 30 days

### Sync conflicts

- Server-wins strategy: server data overwrites local
- Check sync errors in app logs
- Manual retry usually resolves issues

### Permission denied

- Go to Android Settings → Apps → DiaryML → Permissions
- Enable required permissions

## Performance Tips

- Sync happens in background - no need to wait
- Entries are saved locally first (instant save)
- Large entries (>1000 words) may take longer to process moods
- Image uploads not yet implemented (coming soon)

## Backend Requirements

Ensure your DiaryML backend has:

- Mobile API endpoints (`/api/mobile/*`)
- JWT authentication enabled
- `python-jose[cryptography]` installed
- Server accessible on network

## Security

- JWT tokens stored in Flutter Secure Storage
- 30-day token expiration
- Local SQLite database (encrypted coming soon)
- No password storage on device
- HTTPS recommended for production

## Roadmap

- [ ] Image upload with compression
- [ ] Voice notes (audio recordings)
- [ ] Offline mood detection
- [ ] Push notifications for insights
- [ ] Widget for quick entry
- [ ] Biometric authentication
- [ ] End-to-end encryption
- [ ] iOS build

## Support

For issues, check:
1. Flutter logs: `flutter logs`
2. Backend logs: Check uvicorn output
3. Network connectivity
4. Server URL configuration

## License

Same as DiaryML main project
