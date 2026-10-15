package com.novelsite.mobile

import android.content.Context
import android.net.Uri
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject

/** Image content parts for OpenRouter's chat/completions vision API. */
object NativeImageAttachments {
    const val MAX_IMAGES = 20
    private const val MAX_IMAGE_BYTES = 5 * 1024 * 1024

    fun content(context: Context, uris: List<Uri>, prompt: String): JSONArray {
        val parts = JSONArray().put(JSONObject().put("type", "text").put("text", prompt))
        for (uri in uris.take(MAX_IMAGES)) {
            val mime = context.contentResolver.getType(uri)?.lowercase() ?: "image/jpeg"
            require(mime in setOf("image/jpeg", "image/png", "image/webp", "image/gif")) {
                "JPEG・PNG・WebP・GIFのみ添付できます"
            }
            val bytes = context.contentResolver.openInputStream(uri)?.use { stream ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val count = stream.read(buffer)
                    if (count < 0) break
                    require(output.size() + count <= MAX_IMAGE_BYTES) { "画像は1枚5MB以内にしてください" }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            } ?: error("画像を読み込めません")
            val data = "data:$mime;base64," + Base64.encodeToString(bytes, Base64.NO_WRAP)
            parts.put(JSONObject().put("type", "image_url")
                .put("image_url", JSONObject().put("url", data)))
        }
        return parts
    }
}
