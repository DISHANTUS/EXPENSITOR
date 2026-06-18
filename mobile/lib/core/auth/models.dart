/// Hand-written DTOs (no codegen in Sprint 1, so the project compiles with just
/// `flutter pub get`). freezed/json_serializable can be adopted later.
class TokenPair {
  const TokenPair({required this.accessToken, required this.refreshToken});

  factory TokenPair.fromJson(Map<String, dynamic> json) => TokenPair(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String,
      );

  final String accessToken;
  final String refreshToken;
}

class AppUser {
  const AppUser({
    required this.id,
    required this.email,
    this.isDeveloper = false,
    this.hasSeenTour = false,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) => AppUser(
        id: json['id'].toString(),
        email: json['email'] as String,
        isDeveloper: json['is_developer'] == true,
        hasSeenTour: json['has_seen_tour'] == true,
      );

  final String id;
  final String email;
  final bool isDeveloper;   // gates the Developer / Testing tools
  final bool hasSeenTour;   // false → the first-launch tour runs once

  AppUser copyWith({bool? hasSeenTour}) => AppUser(
        id: id,
        email: email,
        isDeveloper: isDeveloper,
        hasSeenTour: hasSeenTour ?? this.hasSeenTour,
      );
}
