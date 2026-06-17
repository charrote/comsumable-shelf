# Keep serialization
-keepattributes *Annotation*
-keep class kotlinx.serialization.** { *; }

# Keep Room entities
-keep class com.smes.pda.data.** { *; }
