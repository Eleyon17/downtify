// LRC (time-synced lyrics) parsing for the Now playing lyrics panel.

const TIME_TAG = /\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]/g

/**
 * Parse LRC text into `[{ time, text }]` sorted by time (seconds).
 * A line with several time tags (`[00:10][00:40]Chorus`) yields one
 * entry per tag; metadata tags (`[ar:...]`) and blank lines are skipped.
 */
export function parseLrc(source, translatedSource = null) {
  const lines = []
  for (const raw of String(source || '').split(/\r?\n/)) {
    const tags = [...raw.matchAll(TIME_TAG)]
    if (!tags.length) continue
    const text = raw.replace(TIME_TAG, '').trim()
    for (const [, min, sec, frac = '0'] of tags) {
      const fraction = Number(frac) / 10 ** frac.length
      lines.push({ time: Number(min) * 60 + Number(sec) + fraction, text })
    }
  }
  lines.sort((a, b) => a.time - b.time)

  if (translatedSource) {
    const tLines = parseLrc(translatedSource)
    if (tLines.length) {
      const tMap = new Map()
      for (const tLine of tLines) {
        const key = Math.round(tLine.time * 10) / 10
        if (!tMap.has(key)) tMap.set(key, tLine.text)
      }
      for (let i = 0; i < lines.length; i++) {
        const key = Math.round(lines[i].time * 10) / 10
        let trans = ''
        if (tMap.has(key)) {
          trans = tMap.get(key)
        } else if (i < tLines.length && Math.abs(lines[i].time - tLines[i].time) < 1.0) {
          trans = tLines[i].text
        } else if (lines.length === tLines.length) {
          trans = tLines[i].text
        }
        if (trans) {
          lines[i].translation = trans
        }
      }
    }
  }

  return lines
}

/** Index of the line being sung at `seconds`, or -1 before the first. */
export function activeLineIndex(lines, seconds) {
  let lo = 0
  let hi = lines.length - 1
  let found = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (lines[mid].time <= seconds) {
      found = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return found
}
