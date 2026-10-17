import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useShares } from '../model/shares'
import API from '../model/api'

vi.mock('../model/api', () => ({
  default: {
    createShare: vi.fn(),
    getPublicShare: vi.fn(),
    listShares: vi.fn(),
    deleteShare: vi.fn(),
  },
}))

vi.mock('../model/ui', () => ({
  useUi: () => ({
    toast: vi.fn(),
  }),
}))

describe('useShares', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    const { closeShareModal } = useShares()
    closeShareModal()
  })

  it('shares a track and opens modal', async () => {
    const fakeShare = {
      id: 'abc123token',
      kind: 'track',
      target: 'Artist - Song.mp3',
      title: 'Song',
      url: 'http://localhost:6125/share/abc123token',
    }
    API.createShare.mockResolvedValueOnce({ data: fakeShare })

    const { shareTrack, shareModalOpen, currentShare } = useShares()
    const result = await shareTrack({ file: 'Artist - Song.mp3', title: 'Song' })

    expect(API.createShare).toHaveBeenCalledWith({
      kind: 'track',
      target: 'Artist - Song.mp3',
      title: 'Song',
    })
    expect(result).toEqual(fakeShare)
    expect(currentShare.value).toEqual(fakeShare)
    expect(shareModalOpen.value).toBe(true)
  })

  it('shares a playlist and opens modal', async () => {
    const fakeShare = {
      id: 'pl123token',
      kind: 'playlist',
      target: 'My Chill Vibes',
      title: 'My Chill Vibes',
      url: 'http://localhost:6125/share/pl123token',
    }
    API.createShare.mockResolvedValueOnce({ data: fakeShare })

    const { sharePlaylist, shareModalOpen, currentShare } = useShares()
    const result = await sharePlaylist({ name: 'My Chill Vibes', title: 'My Chill Vibes' })

    expect(API.createShare).toHaveBeenCalledWith({
      kind: 'playlist',
      target: 'My Chill Vibes',
      title: 'My Chill Vibes',
    })
    expect(result).toEqual(fakeShare)
    expect(currentShare.value).toEqual(fakeShare)
    expect(shareModalOpen.value).toBe(true)
  })

  it('closes share modal', () => {
    const { shareModalOpen, closeShareModal } = useShares()
    shareModalOpen.value = true
    closeShareModal()
    expect(shareModalOpen.value).toBe(false)
  })
})
