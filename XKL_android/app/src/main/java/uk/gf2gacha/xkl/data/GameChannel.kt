package uk.gf2gacha.xkl.data

enum class GameChannel(val id: Int, val label: String) {
    OFFICIAL(5, "官服"),
    BILIBILI(6, "B服");

    fun accountKey(uid: String): String = if (this == OFFICIAL) uid else "bili:$uid"

    companion object {
        fun fromId(id: Int): GameChannel = entries.firstOrNull { it.id == id } ?: OFFICIAL
    }
}

data class SmsChallenge(val phone: String, val channel: GameChannel, val captchaKey: String = "")
