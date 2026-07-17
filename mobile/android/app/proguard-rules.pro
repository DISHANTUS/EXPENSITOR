# ML Kit text recognition (google_mlkit_text_recognition) references optional
# per-script recognizers — Chinese, Devanagari, Japanese, Korean — that we do
# not bundle (we use the default Latin recognizer). R8 fails the release build
# over these "missing" classes; -dontwarn tells it they're intentionally absent.
# Isolated to ML Kit; affects no other plugin. This is the fix the plugin's own
# docs prescribe.
-dontwarn com.google.mlkit.vision.text.chinese.**
-dontwarn com.google.mlkit.vision.text.devanagari.**
-dontwarn com.google.mlkit.vision.text.japanese.**
-dontwarn com.google.mlkit.vision.text.korean.**
-keep class com.google.mlkit.vision.text.** { *; }
