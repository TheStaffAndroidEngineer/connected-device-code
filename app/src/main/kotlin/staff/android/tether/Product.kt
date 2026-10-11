package staff.android.tether
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.Alignment
import androidx.compose.foundation.shape.RoundedCornerShape
import org.json.JSONObject
const val ABOUT="Tether controls a simulated studio thermostat. No Bluetooth radio, scan, pairing or GATT operation runs. Desired settings and acknowledged setpoints remain separate across connection changes and device reboots."
fun validateView(d:JSONObject){
    for (k in
        listOf(
            "boot", "connection", "desired", "reported", "nextSequence", "acknowledged")) require(
        d.get(k) is Int)
    require(d.getInt("boot") > 0 && d.getInt("connection") >= 0 && d.get("connected") is Boolean)
    require(d.getInt("desired") in 16..28 && d.getInt("reported") in 16..28)
    if (!d.isNull("pending")) {
        val p = d.getJSONObject("pending")
        for (k in listOf("boot", "connection", "sequence", "target")) require(p.get(k) is Int)
    }
}
fun grant(d:JSONObject)=JSONObject().put("boot",d.getInt("boot")).put("connection",d.getInt("connection"))
@Composable fun Product(state: CaseState, model: CaseModel, elapsed: Long) {
    Text("Studio thermostat", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
    Text("Simulated device · no Bluetooth connection", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    val data = state.data
    if (data == null) { InfoCard(if (state.busy) "Checking the thermostat" else "Device unavailable", "Connect to the local service and refresh to see the saved settings."); return }
    if (!data.getBoolean("connected")) Button(onClick = { model.send("connect") }, enabled = ready(state), modifier = Modifier.fillMaxWidth().testTag("connect")) { Text("Connect to simulator") }
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        if (maxWidth >= 620.dp) Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            Box(Modifier.weight(1f)) { TemperatureControl(state, model, data) }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(16.dp)) { DeviceReport(state, model, data) }
        } else Column(verticalArrangement = Arrangement.spacedBy(18.dp)) { TemperatureControl(state, model, data); DeviceReport(state, model, data) }
    }
}

@Composable private fun TemperatureControl(state: CaseState, model: CaseModel, data: JSONObject) {
    val primary = MaterialTheme.colorScheme.primary
    val track = MaterialTheme.colorScheme.outlineVariant
    Surface(color = MaterialTheme.colorScheme.surface, shape = RoundedCornerShape(28.dp)) {
        Column(Modifier.fillMaxWidth().padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Box(Modifier.fillMaxWidth().height(240.dp), contentAlignment = Alignment.Center) {
                Canvas(Modifier.fillMaxSize()) {
                    val diameter = minOf(size.width, size.height) * .90f
                    val top = Offset((size.width - diameter) / 2, (size.height - diameter) / 2)
                    val bounds = androidx.compose.ui.geometry.Size(diameter, diameter)
                    drawArc(track, 140f, 260f, false, top, bounds, style = androidx.compose.ui.graphics.drawscope.Stroke(10.dp.toPx(), cap = androidx.compose.ui.graphics.StrokeCap.Round))
                    drawArc(primary, 140f, (data.getInt("desired") - 16) / 12f * 260f, false, top, bounds, style = androidx.compose.ui.graphics.drawscope.Stroke(10.dp.toPx(), cap = androidx.compose.ui.graphics.StrokeCap.Round))
                }
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("Your setting", style = MaterialTheme.typography.labelLarge)
                    Text("${data.getInt("desired")}°C", fontSize = 46.sp, fontWeight = FontWeight.Bold)
                    Text("16–28°C", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                for (delta in listOf(-1, 1)) {
                    val target = (data.getInt("desired") + delta).coerceIn(16, 28)
                    OutlinedButton(onClick = { model.send("set", grant(data).put("target", target)) }, enabled = ready(state) && data.getBoolean("connected") && target != data.getInt("desired"), modifier = Modifier.testTag(if (delta < 0) "lower" else "raise")) { Text(if (delta < 0) "− Cooler" else "+ Warmer") }
                }
            }
        }
    }
}

@Composable private fun DeviceReport(state: CaseState, model: CaseModel, data: JSONObject) {
    val connected = data.getBoolean("connected")
    Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(if (data.getInt("acknowledged") > 0) "DEVICE-CONFIRMED SETPOINT" else "REPORTED DEFAULT SETPOINT", style = MaterialTheme.typography.labelSmall)
            Text("${data.getInt("reported")}°C", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text(when { !connected -> if (data.getInt("acknowledged") > 0) "Disconnected · last confirmation may be stale" else "Disconnected · showing simulator default"; !data.isNull("pending") -> "Waiting for the device to confirm your setting"; data.getInt("desired") != data.getInt("reported") -> "Your setting is not confirmed"; data.getInt("acknowledged") == 0 -> "Simulator default; no command acknowledgement yet"; else -> "Your setting matches the last confirmation" }, style = MaterialTheme.typography.bodyMedium)
            Text("This is a setpoint, not a measured room temperature.", style = MaterialTheme.typography.bodySmall)
        }
    }
    if (connected && data.getInt("desired") != data.getInt("reported") && data.isNull("pending")) Button(onClick = { model.send("set", grant(data).put("target", data.getInt("desired"))) }, enabled = ready(state), modifier = Modifier.fillMaxWidth().testTag("reconcile")) { Text("Apply desired setting again") }
    if (connected) TextButton(onClick = { model.send("disconnect", grant(data)) }, enabled = ready(state), modifier = Modifier.testTag("disconnect")) { Text("Disconnect") }
}
