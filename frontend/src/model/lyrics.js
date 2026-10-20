// Lyrics for the Now playing view (GET /lyrics), cached per file and lang.
import API from '/src/model/api'
import { parseLrc } from '/src/lib/lrc'

const cache = new Map()

/** Resolves `{ lines: [{time, text, translation}], plain: string, translatedPlain: string }` for a track. */
export function loadLyrics(file, lang = '') {
  if (!file) return Promise.resolve({ lines: [], plain: '', translatedPlain: '' })
  const cacheKey = `${file}::${lang || ''}`
  if (!cache.has(cacheKey)) {
    cache.set(
      cacheKey,
      API.getLyrics(file, lang)
        .then((res) => {
          const synced = res.data?.synced
          const translatedSynced = res.data?.translated_synced
          const plain = String(res.data?.plain || '')
          const translatedPlain = String(res.data?.translated_plain || '')
          return {
            lines: parseLrc(synced, translatedSynced),
            plain,
            translatedPlain,
            sourceLang: res.data?.source_lang,
            targetLang: res.data?.target_lang,
          }
        })
        .catch(() => {
          cache.delete(cacheKey)
          return { lines: [], plain: '', translatedPlain: '' }
        })
    )
  }
  return cache.get(cacheKey)
}
