package com.vayutechnologies.cloudsync.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight

private val Ink = Color(0xFF101828)
private val Muted = Color(0xFF5D6B80)
private val Paper = Color(0xFFF3F7FB)
private val Line = Color(0xFFE3EBF5)
private val Orange = Color(0xFFFF9900)
private val OrangeInk = Color(0xFF1C1406)
private val Night = Color(0xFF07111C)
private val NightCard = Color(0xFF141C2E)
private val NightLine = Color(0xFF2C3A52)
private val NightMuted = Color(0xFF9AABC2)
private val NightInk = Color(0xFFF5F8FC)

private val LightColors = lightColorScheme(
    primary = Orange,
    onPrimary = OrangeInk,
    background = Paper,
    onBackground = Ink,
    surface = Color.White,
    onSurface = Ink,
    surfaceVariant = Color.White,
    onSurfaceVariant = Muted,
    outline = Line,
    secondary = Muted,
    onSecondary = Color.White,
)

private val DarkColors = darkColorScheme(
    primary = Orange,
    onPrimary = OrangeInk,
    background = Night,
    onBackground = NightInk,
    surface = NightCard,
    onSurface = NightInk,
    surfaceVariant = NightCard,
    onSurfaceVariant = NightMuted,
    outline = NightLine,
    secondary = NightMuted,
    onSecondary = NightInk,
)

private val Jakarta = FontFamily.SansSerif

private fun styled(base: Typography): Typography {
    fun TextStyle.face() = copy(fontFamily = Jakarta)
    return Typography(
        displayLarge = base.displayLarge.face(),
        displayMedium = base.displayMedium.face(),
        displaySmall = base.displaySmall.face(),
        headlineLarge = base.headlineLarge.face(),
        headlineMedium = base.headlineMedium.face(),
        headlineSmall = base.headlineSmall.face(),
        titleLarge = base.titleLarge.face(),
        titleMedium = base.titleMedium.face(),
        titleSmall = base.titleSmall.face(),
        bodyLarge = base.bodyLarge.face(),
        bodyMedium = base.bodyMedium.face(),
        bodySmall = base.bodySmall.face(),
        labelLarge = base.labelLarge.face(),
        labelMedium = base.labelMedium.face(),
        labelSmall = base.labelSmall.face(),
    )
}

@Composable
fun CloudSyncTheme(dark: Boolean, content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        typography = styled(Typography()),
        content = content,
    )
}
