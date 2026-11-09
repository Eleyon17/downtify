package com.henriquesebastiao.downtify.feature.player

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.IconButtonShapes
import androidx.compose.material3.LoadingIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.henriquesebastiao.downtify.R
import com.henriquesebastiao.downtify.core.designsystem.component.Artwork
import com.henriquesebastiao.downtify.core.designsystem.component.CircleButton
import com.henriquesebastiao.downtify.core.designsystem.component.CoverTheme
import com.henriquesebastiao.downtify.core.designsystem.component.DowntifyIcons
import com.henriquesebastiao.downtify.core.designsystem.component.MarqueeText
import com.henriquesebastiao.downtify.core.designsystem.component.PhonePreviews
import com.henriquesebastiao.downtify.core.designsystem.component.PlaybackControls
import com.henriquesebastiao.downtify.core.designsystem.component.PlaybackLabels
import com.henriquesebastiao.downtify.core.designsystem.component.PlayerToggle
import com.henriquesebastiao.downtify.core.designsystem.component.PlayerToggles
import com.henriquesebastiao.downtify.core.designsystem.component.Tag
import com.henriquesebastiao.downtify.core.designsystem.component.TagTone
import com.henriquesebastiao.downtify.core.designsystem.component.WavySeekBar
import com.henriquesebastiao.downtify.core.designsystem.theme.DowntifyShape
import com.henriquesebastiao.downtify.core.designsystem.theme.DowntifyTheme
import com.henriquesebastiao.downtify.core.designsystem.theme.DowntifyType
import com.henriquesebastiao.downtify.core.designsystem.theme.Spacing
import com.henriquesebastiao.downtify.core.model.PlaybackContext
import com.henriquesebastiao.downtify.core.model.PlaybackContextType
import com.henriquesebastiao.downtify.core.model.Playlist
import com.henriquesebastiao.downtify.core.model.ServerJob
import com.henriquesebastiao.downtify.core.model.ServerJobStatus
import com.henriquesebastiao.downtify.core.model.StreamQuality
import com.henriquesebastiao.downtify.core.model.Track
import com.henriquesebastiao.downtify.core.model.codecLabel
import com.henriquesebastiao.downtify.core.model.formatDuration
import com.henriquesebastiao.downtify.core.model.kilobits
import com.henriquesebastiao.downtify.core.model.kilohertz
import com.henriquesebastiao.downtify.core.network.ServerUrls
import com.henriquesebastiao.downtify.core.network.dto.ArtistOverviewDto
import com.henriquesebastiao.downtify.core.network.dto.ArtistPopularSongDto
import com.henriquesebastiao.downtify.core.network.dto.ArtistTopAlbumDto
import com.henriquesebastiao.downtify.core.player.PlaybackError
import com.henriquesebastiao.downtify.core.player.PlayerState
import com.henriquesebastiao.downtify.core.player.PlayingEpisode
import com.henriquesebastiao.downtify.core.player.RepeatMode
import com.henriquesebastiao.downtify.ui.common.LocalCoverUrls
import com.henriquesebastiao.downtify.ui.common.PreviewData

/** Everything Now Playing can ask for. */
data class NowPlayingActions(
    val onCollapse: () -> Unit = {},
    val onTogglePlay: () -> Unit = {},
    val onNext: () -> Unit = {},
    val onPrevious: () -> Unit = {},
    val onSeek: (Long) -> Unit = {},
    val onToggleShuffle: () -> Unit = {},
    val onCycleRepeat: () -> Unit = {},
    val onToggleLike: () -> Unit = {},
    val onOpenLyrics: () -> Unit = {},
    val onOpenQueue: () -> Unit = {},
    val onOpenContext: (PlaybackContext) -> Unit = {},
    val onSkipBack: () -> Unit = {},
    val onSkipForward: () -> Unit = {},
    val onCycleSpeed: () -> Unit = {},
    val onGoToShow: (Long) -> Unit = {},
    val onGoToArtist: (String) -> Unit = {},
    val onGoToAlbum: (String) -> Unit = {},
    val onOpenSimilar: () -> Unit = {},
    val onQueueTopAlbum: (ArtistTopAlbumDto) -> Unit = {},
    val onDownloadStream: () -> Unit = {},
    /** Moves the synced lyrics this many ms later (earlier when negative). */
    val onShiftLyrics: (Long) -> Unit = {},
    val onResetLyrics: () -> Unit = {},
)

/**
 * Now Playing (v3), in the cover's colors: lyrics and the queue as a pair at the top end, the
 * cover as large as the controls leave room for, the title, the wavy seek bar with the sample
 * rate, bitrate and format between its times, the expressive transport, and the shuffle / repeat
 * / like toggles (beside a stream's download button).
 *
 * [hasLibraryCopy] is true when the playing stream has since been downloaded (a library track
 * matches it, passed as [libraryTrack]): the stream keeps playing, but the buttons switch to
 * the library set (like, lyrics, the artist link) and the download button goes away. A finished
 * server job ([ServerJobStatus.Done]) hides the download button at once; like and lyrics appear
 * with the library sync, when there is a track id behind them to act on. [coverModifier] goes on
 * the cover (it flies from and to the mini player's).
 */
@Composable
fun NowPlayingScreen(
    state: PlayerState,
    isLiked: Boolean,
    serverName: String,
    actions: NowPlayingActions,
    modifier: Modifier = Modifier,
    downloadJob: ServerJob? = null,
    hasLibraryCopy: Boolean = false,
    libraryTrack: Track? = null,
    coverModifier: Modifier = Modifier,
    artistOverview: ArtistOverviewDto? = null,
    editablePlaylists: List<Playlist> = emptyList(),
    onLoadArtistOverview: (String) -> Unit = {},
    onPlayLibraryFile: (String) -> Unit = {},
    onQueueLibraryFile: (String) -> Unit = {},
    onPlayPopularSong: (ArtistPopularSongDto) -> Unit = {},
    onQueuePopularSong: (ArtistPopularSongDto) -> Unit = {},
    onQueueTopAlbum: (ArtistTopAlbumDto) -> Unit = actions.onQueueTopAlbum,
    onAddToPlaylist: (String) -> Unit = {},
    onCreatePlaylistAndAdd: (String, Boolean) -> Unit = { _, _ -> },
    onShareTrack: () -> Unit = {},
) {
    val track = state.track
    val episode = state.episode
    val stream = state.stream
    if (track == null && episode == null && stream == null) return
    val downloaded = hasLibraryCopy || downloadJob?.status == ServerJobStatus.Done
    // Where the artist tap goes: the track's artist, or that of the library copy behind a stream.
    val artistId = (track ?: libraryTrack.takeIf { stream != null })?.artistId.orEmpty()
    val artistName = (track?.displayArtist ?: stream?.artist).orEmpty()
    val coverUrl = playingCoverUrl(state, ServerUrls.COVER_LARGE)
    var flipped by rememberSaveable(track?.id, stream?.videoId) { mutableStateOf(false) }
    var showAddToPlaylistDialog by rememberSaveable { mutableStateOf(false) }

    if (showAddToPlaylistDialog) {
        var newName by rememberSaveable { mutableStateOf("") }
        var newPublic by rememberSaveable { mutableStateOf(false) }
        AlertDialog(
            onDismissRequest = { showAddToPlaylistDialog = false },
            title = { Text("Add to playlist") },
            text = {
                Column(
                    Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(Spacing.xs),
                ) {
                    editablePlaylists.filter { !it.liked }.forEach { pl ->
                        Surface(
                            onClick = {
                                showAddToPlaylistDialog = false
                                onAddToPlaylist(pl.name)
                            },
                            shape = RoundedCornerShape(12.dp),
                            color = MaterialTheme.colorScheme.surfaceContainer,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Row(
                                Modifier.padding(horizontal = Spacing.md, vertical = Spacing.sm),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Text(pl.title, style = MaterialTheme.typography.bodyLarge)
                                Text(
                                    "${pl.trackIds.size}",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                    Spacer(Modifier.height(Spacing.xs))
                    OutlinedTextField(
                        value = newName,
                        onValueChange = { newName = it },
                        label = { Text("Or new playlist name") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(checked = newPublic, onCheckedChange = { newPublic = it })
                        Text("Public playlist", style = MaterialTheme.typography.bodyMedium)
                    }
                }
            },
            confirmButton = {
                if (newName.isNotBlank()) {
                    TextButton(
                        onClick = {
                            showAddToPlaylistDialog = false
                            onCreatePlaylistAndAdd(newName.trim(), newPublic)
                        },
                    ) {
                        Text("Create & Add")
                    }
                }
            },
            dismissButton = {
                TextButton(onClick = { showAddToPlaylistDialog = false }) {
                    Text(stringResource(R.string.action_close))
                }
            },
        )
    }

    CoverTheme(playingCoverUrl(state)) {
        val scheme = MaterialTheme.colorScheme
        Surface(
            color = scheme.primaryContainer,
            contentColor = scheme.onPrimaryContainer,
            modifier = modifier.fillMaxSize(),
        ) {
            BoxWithConstraints(Modifier.fillMaxSize().safeDrawingPadding()) {
                val compact = maxHeight < COMPACT_HEIGHT
                Column(
                    Modifier.fillMaxSize().padding(horizontal = Spacing.lg),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(if (compact) Spacing.sm else Spacing.md),
                ) {
                    Header(
                        context = state.context,
                        episode = episode,
                        actions = actions,
                        lyrics = episode == null && (stream == null || hasLibraryCopy),
                        queue = episode == null,
                        onShareTrack = onShareTrack,
                    )
                    val flipRotation by animateFloatAsState(
                        targetValue = if (flipped && episode == null) 180f else 0f,
                        animationSpec = tween(durationMillis = 450, easing = FastOutSlowInEasing),
                        label = "coverFlipRotation",
                    )
                    // The cover takes whatever the rest leaves, square; smooth 3D flip for Artist Overview & Track Actions.
                    Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                        Box(
                            modifier = Modifier
                                .widthIn(max = MAX_COVER)
                                .fillMaxWidth()
                                .aspectRatio(1f, matchHeightConstraintsFirst = true)
                                .graphicsLayer {
                                    rotationY = flipRotation
                                    cameraDistance = 14f * density
                                },
                        ) {
                            if (flipRotation <= 90f) {
                                Artwork(
                                    url = coverUrl,
                                    contentDescription = null,
                                    shape = DowntifyShape.Artwork,
                                    placeholderIcon = if (episode != null) DowntifyIcons.Podcasts else DowntifyIcons.Song,
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .then(
                                            if (episode == null) {
                                                Modifier.clickable {
                                                    flipped = true
                                                    if (artistName.isNotBlank()) onLoadArtistOverview(artistName)
                                                }
                                            } else {
                                                Modifier
                                            },
                                        )
                                        .then(coverModifier),
                                )
                            } else {
                                ArtistFlipCard(
                                    artistName = artistName,
                                    overview = artistOverview,
                                    hasLibraryTrack = track != null || hasLibraryCopy,
                                    onFlipBack = { flipped = false },
                                    onPlayFile = onPlayLibraryFile,
                                    onQueueFile = onQueueLibraryFile,
                                    onPlayPopularSong = onPlayPopularSong,
                                    onQueuePopularSong = onQueuePopularSong,
                                    onQueueTopAlbum = onQueueTopAlbum,
                                    onGoToAlbum = actions.onGoToAlbum,
                                    onAddToPlaylist = { showAddToPlaylistDialog = true },
                                    onShareTrack = onShareTrack,
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .graphicsLayer {
                                            rotationY = 180f
                                        },
                                )
                            }
                        }
                    }
                    TitleBlock(
                        title = track?.displayTitle ?: stream?.title ?: episode?.title.orEmpty(),
                        artist = track?.displayArtist ?: stream?.artist ?: episode?.showName.orEmpty(),
                        onArtist = when {
                            episode != null -> ({ actions.onGoToShow(episode.showId) })
                            artistId.isNotEmpty() -> ({ actions.onGoToArtist(artistId) })
                            else -> null
                        },
                    )
                    SeekBar(state, actions.onSeek, formatOf(track, state))
                    if (episode != null) {
                        EpisodeTransport(state, actions, compact)
                    } else {
                        TrackTransport(
                            state = state,
                            actions = actions,
                            compact = compact,
                            isLiked = isLiked.takeIf { stream == null || hasLibraryCopy },
                            trailing = if (stream != null && !downloaded) {
                                {
                                    StreamDownloadButton(
                                        job = downloadJob,
                                        title = stream.title,
                                        onDownload = actions.onDownloadStream,
                                    )
                                }
                            } else {
                                null
                            },
                        )
                    }
                    SourceLines(state, track, serverName)
                }
            }
        }
    }
}

/**
 * The top row: collapse, where it plays from (tap to go there) — or just "Now playing" when that's
 * the whole library or nowhere in particular — and lyrics and the queue as a pair of buttons,
 * round outside, at the end. A stream with no library copy has no lyrics: the queue stands alone.
 * An episode has neither.
 */
@Composable
private fun Header(
    context: PlaybackContext?,
    episode: PlayingEpisode?,
    actions: NowPlayingActions,
    lyrics: Boolean,
    queue: Boolean,
    onShareTrack: () -> Unit = {},
) {
    Row(
        Modifier.fillMaxWidth().height(64.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Spacing.md),
    ) {
        CircleButton(
            DowntifyIcons.Collapse,
            stringResource(R.string.player_close),
            actions.onCollapse,
            containerColor = playerTint(),
            contentColor = playerContent(),
        )
        val from = context?.type?.let(::playingFromLabel)
        Column(
            Modifier
                .weight(1f)
                .then(
                    when {
                        episode != null -> Modifier.clickable { actions.onGoToShow(episode.showId) }
                        context != null && from != null -> Modifier.clickable { actions.onOpenContext(context) }
                        else -> Modifier
                    },
                ),
        ) {
            val (overline, title) = when {
                episode != null -> stringResource(R.string.player_playing_from_podcast) to episode.showName
                context != null && from != null -> stringResource(from) to context.title
                else -> null to stringResource(R.string.player_now_playing)
            }
            if (overline != null) {
                Text(
                    overline.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.alpha(MUTED_ALPHA),
                )
            }
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(Spacing.xs)) {
            HeaderButton(
                DowntifyIcons.Share,
                "Share",
                onShareTrack,
                CircleShape,
            )
            if (lyrics) {
                HeaderButton(
                    DowntifyIcons.Lyrics,
                    stringResource(R.string.player_lyrics),
                    actions.onOpenLyrics,
                    if (queue) DowntifyShape.PairStart else CircleShape,
                )
            }
            if (queue) {
                HeaderButton(
                    DowntifyIcons.Queue,
                    stringResource(R.string.player_queue),
                    actions.onOpenQueue,
                    if (lyrics) DowntifyShape.PairEnd else CircleShape,
                )
            }
        }
    }
}

/** One of the header's pair: 56 × 48 dp, in the collapse button's tint, squarer while pressed. */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun HeaderButton(icon: Int, label: String, onClick: () -> Unit, shape: Shape) {
    FilledTonalIconButton(
        onClick = onClick,
        shapes = IconButtonShapes(shape = shape, pressedShape = RoundedCornerShape(12.dp)),
        colors = IconButtonDefaults.filledTonalIconButtonColors(
            containerColor = playerTint(),
            contentColor = playerContent(),
        ),
        modifier = Modifier.size(width = 56.dp, height = 48.dp),
    ) {
        Icon(painterResource(icon), contentDescription = label)
    }
}

/**
 * The title and the artist (or the show), centred. One that doesn't fit slides, fading in and out
 * at both ends, so it stays readable.
 */
@Composable
private fun TitleBlock(title: String, artist: String, onArtist: (() -> Unit)?) {
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        MarqueeText(title, style = MaterialTheme.typography.headlineMediumEmphasized)
        MarqueeText(
            artist,
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier
                .alpha(SUBTITLE_ALPHA)
                .then(if (onArtist != null) Modifier.clickable(onClick = onArtist) else Modifier),
        )
    }
}

@Composable
private fun SeekBar(state: PlayerState, onSeek: (Long) -> Unit, format: String?) {
    val duration = state.durationMs.coerceAtLeast(1)
    WavySeekBar(
        progress = state.positionMs.toFloat() / duration,
        onSeek = { onSeek((it * duration).toLong()) },
        playing = state.isPlaying,
        timeAt = { formatDuration((it * duration).toLong() / 1000.0) },
        duration = formatDuration(state.durationMs / 1000.0),
        contentDescription = stringResource(R.string.player_seek),
        between = format?.let { { Tag(it, tone = TagTone.OnColor, small = true) } },
    )
}

/** What the transport button says, for both kinds of item. */
@Composable
private fun transportLabels(previous: Int, next: Int) = PlaybackLabels(
    play = stringResource(R.string.player_play),
    pause = stringResource(R.string.player_pause),
    previous = stringResource(previous),
    next = stringResource(next),
)

/**
 * A song's transport and its toggles: shuffle, repeat and, when there is something to like
 * ([isLiked] not null: a library track), like. Now Playing and the queue share it. Now Playing
 * puts a stream's download button after the toggles ([trailing]), in a 48 dp slot matched by an
 * empty one before them so the toggles stay centred.
 */
@Composable
internal fun TrackTransport(
    state: PlayerState,
    actions: NowPlayingActions,
    compact: Boolean,
    isLiked: Boolean?,
    trailing: (@Composable () -> Unit)? = null,
) {
    PlaybackControls(
        playing = state.isPlaying,
        onTogglePlay = actions.onTogglePlay,
        onPrevious = actions.onPrevious,
        onNext = actions.onNext,
        labels = transportLabels(R.string.player_previous, R.string.player_next),
        compact = compact,
    )
    val toggles = buildList {
        add(
            PlayerToggle(
                icon = DowntifyIcons.Shuffle,
                label = stringResource(if (state.shuffle) R.string.player_shuffle_on else R.string.player_shuffle_off),
                checked = state.shuffle,
                onClick = actions.onToggleShuffle,
            ),
        )
        add(
            PlayerToggle(
                icon = if (state.repeat == RepeatMode.One) DowntifyIcons.RepeatOne else DowntifyIcons.Repeat,
                label = stringResource(
                    when (state.repeat) {
                        RepeatMode.Off -> R.string.player_repeat_off
                        RepeatMode.All -> R.string.player_repeat_all
                        RepeatMode.One -> R.string.player_repeat_one
                    },
                ),
                checked = state.repeat != RepeatMode.Off,
                onClick = actions.onCycleRepeat,
            ),
        )
        // Nothing to like on a stream the library doesn't have yet.
        if (isLiked != null) {
            add(
                PlayerToggle(
                    icon = if (isLiked) DowntifyIcons.FavoriteFilled else DowntifyIcons.Favorite,
                    label = stringResource(if (isLiked) R.string.player_unlike else R.string.player_like),
                    checked = isLiked,
                    onClick = actions.onToggleLike,
                ),
            )
        }
        add(
            PlayerToggle(
                icon = DowntifyIcons.Explore,
                label = stringResource(R.string.similar_find),
                checked = false,
                onClick = actions.onOpenSimilar,
            ),
        )
    }
    if (trailing == null) {
        PlayerToggles(toggles, Modifier.fillMaxWidth(TOGGLES_WIDTH))
    } else {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            Spacer(Modifier.size(48.dp))
            PlayerToggles(toggles, Modifier.weight(1f))
            Box(Modifier.size(48.dp), contentAlignment = Alignment.Center) { trailing() }
        }
    }
}

/** An episode: 10 s back, play, 30 s forward, and its speed — no shuffle, repeat or like. */
@Composable
private fun EpisodeTransport(state: PlayerState, actions: NowPlayingActions, compact: Boolean) {
    PlaybackControls(
        playing = state.isPlaying,
        onTogglePlay = actions.onTogglePlay,
        onPrevious = actions.onSkipBack,
        onNext = actions.onSkipForward,
        labels = transportLabels(R.string.player_skip_back, R.string.player_skip_forward),
        compact = compact,
        previousIcon = DowntifyIcons.SkipBack,
        nextIcon = DowntifyIcons.SkipForward,
    )
    val speedText = speedLabel(state.speed)
    val speedDescription = stringResource(R.string.player_speed, speedText)
    FilledTonalButton(
        onClick = actions.onCycleSpeed,
        colors = ButtonDefaults.filledTonalButtonColors(
            containerColor = playerTint(),
            contentColor = playerContent(),
        ),
        modifier = Modifier.heightIn(min = 56.dp).semantics { contentDescription = speedDescription },
    ) {
        Text(speedText, style = DowntifyType.dataMedium)
    }
}

/** `1×`, `1.25×`: no trailing zeros. */
private fun speedLabel(speed: Float): String =
    (if (speed % 1f == 0f) speed.toInt().toString() else speed.toString()) + "×"

/** Download the playing stream to the server, then what the server is doing with it. */
@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun StreamDownloadButton(job: ServerJob?, title: String, onDownload: () -> Unit) {
    val tint = playerTint()
    val content = playerContent()
    when (job?.status) {
        null -> CircleButton(
            DowntifyIcons.Downloads,
            stringResource(R.string.search_download_to_server, title),
            onDownload,
            containerColor = tint,
            contentColor = content,
        )

        ServerJobStatus.Queued, ServerJobStatus.Downloading -> {
            val label = stringResource(
                if (job.status ==
                    ServerJobStatus.Queued
                ) {
                    R.string.search_job_queued
                } else {
                    R.string.search_job_downloading
                },
            )
            Box(Modifier.size(48.dp).semantics { contentDescription = label }, contentAlignment = Alignment.Center) {
                LoadingIndicator(color = content, modifier = Modifier.size(40.dp))
            }
        }

        ServerJobStatus.Done -> Icon(
            painterResource(DowntifyIcons.CheckCircle),
            contentDescription = stringResource(R.string.search_job_done),
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(48.dp).padding(12.dp),
        )

        ServerJobStatus.Error -> CircleButton(
            DowntifyIcons.Error,
            stringResource(R.string.search_job_error),
            onDownload,
            containerColor = MaterialTheme.colorScheme.errorContainer,
            contentColor = MaterialTheme.colorScheme.onErrorContainer,
        )
    }
}

/** Where it plays from, the offline buffer and the last error, under everything else. */
@Composable
private fun SourceLines(state: PlayerState, track: Track?, serverName: String) {
    Column(
        Modifier.fillMaxWidth().padding(bottom = Spacing.sm),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(Spacing.xs),
    ) {
        Text(
            when {
                track != null -> sourceLine(serverName, state.quality, state.fromPhone)
                state.stream != null -> stringResource(R.string.player_source_stream, serverName)
                else -> stringResource(R.string.player_source_unknown, serverName)
            },
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
            modifier = Modifier.alpha(MUTED_ALPHA),
        )
        state.error?.let { error ->
            Text(
                errorText(error),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
                textAlign = TextAlign.Center,
            )
        }
    }
}

/** "Playing from album" and the like; nothing for the whole library (or search results). */
private fun playingFromLabel(type: PlaybackContextType): Int? = when (type) {
    PlaybackContextType.Album -> R.string.player_playing_from_album
    PlaybackContextType.Artist -> R.string.player_playing_from_artist
    PlaybackContextType.Playlist, PlaybackContextType.Liked -> R.string.player_playing_from_playlist
    PlaybackContextType.Songs -> null
}

@Composable
private fun sourceLine(server: String, quality: StreamQuality?, fromPhone: Boolean): String = when {
    fromPhone -> stringResource(R.string.player_source_this_phone)
    quality?.isOriginal == true -> stringResource(R.string.player_source_original_quality, server)
    else -> stringResource(R.string.player_source_unknown, server)
}

/**
 * What plays, for the tag between the times: `44.1 kHz · 941 kbps · FLAC` for the file (from the
 * server or the phone's copy), or the bitrate and codec the server converts it to (its sample rate
 * isn't known then). A value the library doesn't have is left out. Unknown (a stream, an episode,
 * before the server says how it streams): no tag.
 */
@Composable
private fun formatOf(track: Track?, state: PlayerState): String? {
    if (track == null) return null
    val quality = state.quality
    val (sampleRate, kbps, codec) = when {
        quality != null && !quality.isOriginal && !state.fromPhone -> Triple(
            0,
            quality.bitrate,
            quality.format.wireName,
        )

        state.fromPhone || quality != null -> Triple(track.sampleRate, kilobits(track.bitrate), track.codec)

        else -> return null
    }
    return listOfNotNull(
        sampleRate.takeIf { it > 0 }?.let { stringResource(R.string.player_sample_rate, kilohertz(it)) },
        kbps.takeIf { it > 0 }?.let { stringResource(R.string.player_bitrate, it) },
        codec.takeIf { it.isNotBlank() }?.let(::codecLabel),
    ).joinToString(" · ").ifEmpty { null }
}

@Composable
private fun errorText(error: PlaybackError): String = stringResource(
    when (error) {
        PlaybackError.Network, PlaybackError.Unauthorized -> R.string.player_error_network
        PlaybackError.NotFound -> R.string.player_error_not_found
        PlaybackError.OldServer -> R.string.player_error_old_server
        PlaybackError.Other -> R.string.player_error_other
    },
)

/** The player's round buttons: a wash of the content color on the cover's background. */
@Composable
internal fun playerTint(): Color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = TINT_ALPHA)

/** The player's text and icons on the cover's background. */
@Composable
internal fun playerContent(): Color = MaterialTheme.colorScheme.onPrimaryContainer

@Composable
private fun ArtistFlipCard(
    artistName: String,
    overview: ArtistOverviewDto?,
    hasLibraryTrack: Boolean,
    onFlipBack: () -> Unit,
    onPlayFile: (String) -> Unit,
    onQueueFile: (String) -> Unit,
    onPlayPopularSong: (ArtistPopularSongDto) -> Unit = {},
    onQueuePopularSong: (ArtistPopularSongDto) -> Unit = {},
    onQueueTopAlbum: (ArtistTopAlbumDto) -> Unit = {},
    onGoToAlbum: (String) -> Unit = {},
    onAddToPlaylist: () -> Unit,
    onShareTrack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val covers = LocalCoverUrls.current
    val scheme = MaterialTheme.colorScheme
    val songs = overview?.allSongs.orEmpty()
    val albums = overview?.topAlbums.orEmpty()
    Surface(
        color = scheme.surfaceContainerHigh.copy(alpha = 0.94f),
        contentColor = scheme.onSurface,
        shape = DowntifyShape.Artwork,
        modifier = modifier,
    ) {
        Column(
            Modifier.fillMaxSize().padding(Spacing.md),
            verticalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
            ) {
                Artwork(
                    url = covers.artistPhoto(artistName),
                    fallbackUrl = overview?.displayImage?.takeIf { it.isNotBlank() },
                    contentDescription = artistName,
                    shape = CircleShape,
                    placeholderIcon = DowntifyIcons.Artist,
                    modifier = Modifier.size(44.dp),
                )
                Column(Modifier.weight(1f)) {
                    Text(
                        text = artistName.ifBlank { "Artist" },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (overview != null && overview.bioSource.isNotBlank()) {
                        Text(
                            text = if (overview.bioSource == "youtubemusic") "YouTube Music" else "Artist Profile",
                            style = MaterialTheme.typography.labelSmall,
                            color = scheme.onSurfaceVariant,
                        )
                    } else if ((overview?.fans ?: 0) > 0) {
                        Text(
                            text = "${overview?.fans} fans",
                            style = MaterialTheme.typography.labelSmall,
                            color = scheme.onSurfaceVariant,
                        )
                    }
                }
                TextButton(onClick = onFlipBack) {
                    Text("Cover")
                }
            }
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
            ) {
                AssistChip(
                    onClick = onAddToPlaylist,
                    label = { Text("+ Playlist") },
                )
                AssistChip(
                    onClick = onShareTrack,
                    label = { Text("Share") },
                    leadingIcon = {
                        Icon(painterResource(DowntifyIcons.Share), contentDescription = null, modifier = Modifier.size(16.dp))
                    },
                )
            }
            Column(
                Modifier.weight(1f).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(Spacing.sm),
            ) {
                if (overview == null) {
                    Text(
                        text = "Loading artist overview…",
                        style = MaterialTheme.typography.bodySmall,
                        color = scheme.onSurfaceVariant,
                    )
                } else {
                    if (overview.bio.isNotBlank()) {
                        Text(
                            text = overview.bio,
                            style = MaterialTheme.typography.bodySmall,
                            color = scheme.onSurfaceVariant,
                            maxLines = 6,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    if (songs.isNotEmpty()) {
                        Text(
                            text = "Popular Songs",
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.Bold,
                            color = scheme.primary,
                            modifier = Modifier.padding(top = Spacing.xs),
                        )
                        songs.take(8).forEach { song ->
                            Surface(
                                onClick = {
                                    val f = song.localFile
                                    if (!f.isNullOrBlank()) onPlayFile(f)
                                    else onPlayPopularSong(song)
                                },
                                shape = RoundedCornerShape(12.dp),
                                color = scheme.surfaceContainer,
                                modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
                            ) {
                                Row(
                                    Modifier.padding(horizontal = Spacing.sm, vertical = 6.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                                ) {
                                    Artwork(
                                        url = song.displayCover.takeIf { it.isNotBlank() },
                                        contentDescription = song.displayTitle,
                                        shape = RoundedCornerShape(6.dp),
                                        placeholderIcon = DowntifyIcons.Song,
                                        modifier = Modifier.size(38.dp),
                                    )
                                    Column(Modifier.weight(1f)) {
                                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                            Text(
                                                text = song.displayTitle,
                                                style = MaterialTheme.typography.bodyMedium,
                                                fontWeight = FontWeight.SemiBold,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis,
                                                modifier = Modifier.weight(1f, fill = false),
                                            )
                                            if (song.inLibrary) {
                                                Icon(
                                                    painter = painterResource(DowntifyIcons.Cloud),
                                                    contentDescription = "In library",
                                                    tint = scheme.primary,
                                                    modifier = Modifier.size(14.dp),
                                                )
                                            }
                                        }
                                        val details = listOfNotNull(
                                            song.displayAlbum.takeIf { it.isNotBlank() },
                                            if (song.duration > 0) formatDuration(song.duration) else null,
                                        ).joinToString(" · ")
                                        if (details.isNotBlank()) {
                                            Text(
                                                text = details,
                                                style = MaterialTheme.typography.bodySmall,
                                                color = scheme.onSurfaceVariant,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis,
                                            )
                                        }
                                    }
                                    IconButton(
                                        onClick = {
                                            val f = song.localFile
                                            if (!f.isNullOrBlank()) onQueueFile(f)
                                            else onQueuePopularSong(song)
                                        },
                                        modifier = Modifier.size(32.dp),
                                    ) {
                                        Icon(
                                            painter = painterResource(DowntifyIcons.AddToQueue),
                                            contentDescription = "Play next",
                                            tint = scheme.onSurfaceVariant,
                                            modifier = Modifier.size(18.dp),
                                        )
                                    }
                                }
                            }
                        }
                    }
                    if (albums.isNotEmpty()) {
                        Text(
                            text = "Top Albums",
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.Bold,
                            color = scheme.primary,
                            modifier = Modifier.padding(top = Spacing.xs),
                        )
                        albums.take(6).forEach { alb ->
                            Surface(
                                onClick = {
                                    onQueueTopAlbum(alb)
                                },
                                shape = RoundedCornerShape(12.dp),
                                color = scheme.surfaceContainer,
                                modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
                            ) {
                                Row(
                                    Modifier.padding(horizontal = Spacing.sm, vertical = 6.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                                ) {
                                    Artwork(
                                        url = alb.displayCover.takeIf { it.isNotBlank() },
                                        contentDescription = alb.displayTitle,
                                        shape = RoundedCornerShape(6.dp),
                                        placeholderIcon = DowntifyIcons.Album,
                                        modifier = Modifier.size(38.dp),
                                    )
                                    Column(Modifier.weight(1f)) {
                                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                            Text(
                                                text = alb.displayTitle,
                                                style = MaterialTheme.typography.bodyMedium,
                                                fontWeight = FontWeight.SemiBold,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis,
                                                modifier = Modifier.weight(1f, fill = false),
                                            )
                                            if (alb.inLibrary) {
                                                Icon(
                                                    painter = painterResource(DowntifyIcons.Cloud),
                                                    contentDescription = "In library",
                                                    tint = scheme.primary,
                                                    modifier = Modifier.size(14.dp),
                                                )
                                            }
                                        }
                                        val details = listOfNotNull(
                                            alb.recordType.replaceFirstChar { it.uppercase() }.takeIf { it.isNotBlank() },
                                            alb.year.takeIf { it.isNotBlank() },
                                        ).joinToString(" · ")
                                        if (details.isNotBlank()) {
                                            Text(
                                                text = details,
                                                style = MaterialTheme.typography.bodySmall,
                                                color = scheme.onSurfaceVariant,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis,
                                            )
                                        }
                                    }
                                    IconButton(
                                        onClick = { onQueueTopAlbum(alb) },
                                        modifier = Modifier.size(32.dp),
                                    ) {
                                        Icon(
                                            painter = painterResource(DowntifyIcons.AddToQueue),
                                            contentDescription = "Add album to queue",
                                            tint = scheme.onSurfaceVariant,
                                            modifier = Modifier.size(18.dp),
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

private val COMPACT_HEIGHT = 720.dp
private val MAX_COVER = 420.dp
private const val TOGGLES_WIDTH = 0.92f
private const val TINT_ALPHA = 0.12f
private const val MUTED_ALPHA = 0.72f
private const val SUBTITLE_ALPHA = 0.8f

@PhonePreviews
@Composable
private fun NowPlayingPreview() {
    DowntifyTheme {
        NowPlayingScreen(
            state = PlayerState(
                track = PreviewData.tracks[1],
                isPlaying = true,
                positionMs = 70_000,
                durationMs = 239_000,
                context = PlaybackContext(PlaybackContextType.Album, "alb-Glass Harbor", "Glass Harbor"),
                quality = StreamQuality.Original,
            ),
            isLiked = true,
            serverName = "nas.local",
            actions = NowPlayingActions(),
        )
    }
}

@PhonePreviews
@Composable
private fun NowPlayingEpisodePreview() {
    DowntifyTheme {
        NowPlayingScreen(
            state = PlayerState(
                episode = PlayingEpisode(7, 1, "The Sweetest Thing", "Radiolab", "", "Podcasts/R/e.mp3"),
                isPlaying = false,
                positionMs = 83_000,
                durationMs = 1_862_000,
                speed = 1.25f,
            ),
            isLiked = false,
            serverName = "nas.local",
            actions = NowPlayingActions(),
        )
    }
}
