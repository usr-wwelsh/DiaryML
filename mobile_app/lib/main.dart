import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'services/api_client.dart';
import 'services/local_database.dart';
import 'services/sync_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize API client and load saved server URL
  final apiClient = ApiClient();
  await apiClient.initialize();

  runApp(DiaryMLApp(apiClient: apiClient));
}

class DiaryMLApp extends StatelessWidget {
  final ApiClient apiClient;

  const DiaryMLApp({super.key, required this.apiClient});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        // Services
        Provider<ApiClient>.value(
          value: apiClient,
        ),
        Provider<LocalDatabase>(
          create: (_) => LocalDatabase.instance,
        ),
        ProxyProvider2<ApiClient, LocalDatabase, SyncService>(
          update: (_, apiClient, localDb, __) => SyncService(
            apiClient: apiClient,
            localDb: localDb,
          ),
        ),
      ],
      child: MaterialApp(
        title: 'DiaryML',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          primarySwatch: Colors.deepPurple,
          useMaterial3: true,
          brightness: Brightness.dark,
          scaffoldBackgroundColor: const Color(0xFF0A0E21),
          cardColor: const Color(0xFF1D1E33),
          colorScheme: const ColorScheme.dark(
            primary: Color(0xFF6C5CE7),
            secondary: Color(0xFFA29BFE),
            surface: Color(0xFF1D1E33),
            background: Color(0xFF0A0E21),
          ),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF1D1E33),
            elevation: 0,
          ),
          cardTheme: CardThemeData(
            color: const Color(0xFF1D1E33),
            elevation: 2,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: const Color(0xFF1D1E33),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
            contentPadding: const EdgeInsets.all(16),
          ),
        ),
        home: const LoginScreen(),
      ),
    );
  }
}
