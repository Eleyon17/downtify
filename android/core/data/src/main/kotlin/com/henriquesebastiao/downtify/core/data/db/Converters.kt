package com.henriquesebastiao.downtify.core.data.db

import androidx.room.TypeConverter

internal class Converters {
    @TypeConverter
    fun fromList(value: List<String>): String = value.joinToString(SEPARATOR)

    @TypeConverter
    fun toList(value: String): List<String> = if (value.isEmpty()) emptyList() else value.split(SEPARATOR)

    private companion object {
        /** Unit separator: never in a tag or a track id. */
        const val SEPARATOR = "\u001F"
    }
}
