package com.henriquesebastiao.downtify.feature.collection

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsBottomHeight
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.IconButtonShapes
import androidx.compose.material3.LoadingIndicator
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.henriquesebastiao.downtify.R
import com.henriquesebastiao.downtify.core.designsystem.component.Artwork
import com.henriquesebastiao.downtify.core.designsystem.component.ArtworkTone
import com.henriquesebastiao.downtify.core.designsystem.component.CircleButton
import com.henriquesebastiao.downtify.core.designsystem.component.CoverTheme
import com.henriquesebastiao.downtify.core.designsystem.component.DowntifyIcons
import com.henriquesebastiao.downtify.core.designsystem.component.EmptyState
import com.henriquesebastiao.downtify.core.designsystem.component.PhonePreviews
import com.henriquesebastiao.downtify.core.designsystem.component.Tag
import com.henriquesebastiao.downtify.core.designsystem.component.TagTone
import com.henriquesebastiao.downtify.core.designsystem.component.VerticalScrollbar
import com.henriquesebastiao.downtify.core.designsystem.theme.DowntifyShape
import com.henriquesebastiao.downtify.core.designsystem.theme.DowntifyTheme
import com.henriquesebastiao.downtify.core.designsystem.theme.ListStyle
import com.henriquesebastiao.downtify.core.designsystem.theme.Spacing
import com.henriquesebastiao.downtify.core.model.Track
import com.henriquesebastiao.downtify.core.model.totalMinutes
import com.henriquesebastiao.downtify.core.network.ServerUrls
import com.henriquesebastiao.downtify.core.network.dto.PlaylistSuggestionItemDto
import com.henriquesebastiao.downtify.feature.trash.LocalMoveToTrash
import com.henriquesebastiao.downtify.ui.common.LocalBottomBarsInset
import com.henriquesebastiao.downtify.ui.common.LocalCoverUrls
import com.henriquesebastiao.downtify.ui.common.PreviewData
import com.henriquesebastiao.downtify.ui.common.TrackActions
import com.henriquesebastiao.downtify.ui.common.TrackItem
import com.henriquesebastiao.downtify.ui.common.plusBottomBars
import com.henriquesebastiao.downtify.ui.common.songsCount
import kotlinx.coroutines.launch

@Composable
private fun BoxScope.Scrollbar(state: LazyListState) {}

data class PlaylistManageActions(
    val onToggleVisibility: () -> Unit = {},
    val onClone: (String) -> Unit = {},
    val onToggleHidden: () -> Unit = {},
    val onRename: (String) -> Unit = {},
    val onDelete: () -> Unit = {},
    val onLoadSuggestions: () -> Unit = {},
    val onAddSuggestion: (PlaylistSuggestionItemDto) -> Unit = {},
    val onPlaySuggestion: (PlaylistSuggestionItemDto) -> Unit = {},
    val onLoadUsers: () -> Unit = {},
    val onChangeOwner: (Int) -> Unit = {},
    val onShare: () -> Unit = {},
)

@Composable
fun CollectionRoute(
    onBack: () -> Unit,
    onArtist: (String) -> Unit,
    onAlbum: (String) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: CollectionViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val favoriteBusy by viewModel.favoriteBusy.collectAsStateWithLifecycle()
    val favoriteError by viewModel.favoriteError.collectAsStateWithLifecycle()
    val suggestions by viewModel.suggestions.collectAsStateWithLifecycle()
    val loadingSuggestions by viewModel.loadingSuggestions.collectAsStateWithLifecycle()
    val addingSuggestionIds by viewModel.addingSuggestionIds.collectAsStateWithLifecycle()
    val addedSuggestionIds by viewModel.addedSuggestionIds.collectAsStateWithLifecycle()
    val users by viewModel.users.collectAsStateWithLifecycle()
    val playlists by viewModel.playlists.collectAsStateWithLifecycle()
    val context = LocalContext.current
    var playlistTargetTrack by remember { mutableStateOf<Track?>(null) }

    val canEditPlaylist = state.kind == CollectionKind.Playlist &&
        (state.playlist?.isOwner == true || state.playlist?.canEdit == true)

    CollectionScreen(
        state = state.copy(
            favoriteBusy = favoriteBusy,
            favoriteError = favoriteError,
            suggestions = suggestions,
            loadingSuggestions = loadingSuggestions,
            addingSuggestionIds = addingSuggestionIds,
            addedSuggestionIds = addedSuggestionIds,
            users = users,
        ),
        onBack = onBack,
        onArtist = onArtist,
        onPlay = viewModel::play,
        onPlayOrPause = viewModel::playOrPause,
        onShuffle = viewModel::shuffle,
        onToggleOffline = viewModel::toggleOffline,
        trackActions = TrackActions(
            onToggleLike = viewModel::toggleLike,
            onAddToQueue = viewModel::addToQueue,
            onGoToAlbum = if (state.kind == CollectionKind.Album) null else { t -> onAlbum(t.albumId) },
            onGoToArtist = { onArtist(it.artistId) },
            onMoveToTrash = LocalMoveToTrash.current,
            onAddToPlaylist = { playlistTargetTrack = it },
            onRemoveFromPlaylist = if (canEditPlaylist) viewModel::removeTrackFromPlaylist else null,
            onShare = { t ->
                viewModel.shareTrack(t) { url ->
                    val intent = Intent(Intent.ACTION_SEND).apply {
                        type = "text/plain"
                        putExtra(Intent.EXTRA_SUBJECT, t.displayTitle)
                        putExtra(Intent.EXTRA_TEXT, url)
                    }
                    runCatching { context.startActivity(Intent.createChooser(intent, t.displayTitle)) }
                }
            },
        ),
        modifier = modifier,
        onToggleFavorite = viewModel::toggleFavorite,
        onShareCollection = {
            viewModel.shareCollection { url ->
                val intent = Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(Intent.EXTRA_SUBJECT, state.title)
                    putExtra(Intent.EXTRA_TEXT, url)
                }
                runCatching { context.startActivity(Intent.createChooser(intent, state.title)) }
            }
        },
        playlistActions = if (state.kind == CollectionKind.Playlist) {
            PlaylistManageActions(
                onToggleVisibility = viewModel::toggleVisibility,
                onClone = viewModel::clonePlaylist,
                onToggleHidden = viewModel::toggleHidden,
                onRename = viewModel::renamePlaylist,
                onDelete = { viewModel.deletePlaylist(onBack) },
                onLoadSuggestions = viewModel::loadSuggestions,
                onAddSuggestion = viewModel::addSuggestedSong,
                onPlaySuggestion = viewModel::playSuggestedSong,
                onLoadUsers = viewModel::loadUsers,
                onChangeOwner = viewModel::changeOwner,
                onShare = {
                    viewModel.shareCollection { url ->
                        val intent = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_SUBJECT, state.title)
                            putExtra(Intent.EXTRA_TEXT, url)
                        }
                        runCatching { context.startActivity(Intent.createChooser(intent, state.title)) }
                    }
                },
            )
        } else {
            null
        },
    )

    playlistTargetTrack?.let { track ->
        val editable = playlists.filter { it.canEdit || it.isOwner }
        AlertDialog(
            onDismissRequest = { playlistTargetTrack = null },
            title = { Text("Add to playlist") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (editable.isEmpty()) {
                        Text("No editable playlists found.")
                    } else {
                        editable.forEach { pl ->
                            TextButton(
                                onClick = {
                                    viewModel.addTrackToPlaylist(pl.name, track)
                                    playlistTargetTrack = null
                                },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text(pl.title.ifBlank { pl.name }, modifier = Modifier.fillMaxWidth())
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { playlistTargetTrack = null }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }
}

/**
 * An album, a playlist or Liked songs (v3): the header and its top bar take the cover's colors
 * ([CoverTheme]), fading into the app's surface; the songs are cards of a separated list in the
 * app's own scheme (pure black included), the duration of each in tabular figures.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun CollectionScreen(
    state: CollectionUiState,
    onBack: () -> Unit,
    onArtist: (String) -> Unit,
    onPlay: (Int) -> Unit,
    onPlayOrPause: () -> Unit,
    onShuffle: () -> Unit,
    modifier: Modifier = Modifier,
    onToggleOffline: () -> Unit = {},
    trackActions: TrackActions = TrackActions(),
    onToggleFavorite: () -> Unit = {},
    playlistActions: PlaylistManageActions? = null,
    onShareCollection: () -> Unit = { playlistActions?.onShare?.invoke() },
) {
    val covers = LocalCoverUrls.current
    val coverUrl = state.playlist?.let { covers.playlist(it, state.coverTrackId, ServerUrls.COVER_LARGE) }
        ?: covers.track(state.coverTrackId, ServerUrls.COVER_LARGE)
    val seedUrl = covers.track(state.coverTrackId, ServerUrls.COVER_SMALL)
    val title = if (state.kind == CollectionKind.Liked) stringResource(R.string.liked_songs) else state.title
    // Captured outside the cover's theme: the header fades into the app's surface, not the cover's.
    val appSurface = MaterialTheme.colorScheme.surface
    val list = rememberLazyListState()
    val scope = rememberCoroutineScope()
    var menuExpanded by remember { mutableStateOf(false) }
    var showCloneDialog by remember { mutableStateOf(false) }
    var showRenameDialog by remember { mutableStateOf(false) }
    var showDeleteDialog by remember { mutableStateOf(false) }
    var showOwnerDialog by remember { mutableStateOf(false) }

    Scaffold(
        modifier = modifier,
        contentWindowInsets = WindowInsets(0),
        topBar = {
            CoverTheme(seedUrl) {
                val scheme = MaterialTheme.colorScheme
                TopAppBar(
                    title = {},
                    navigationIcon = {
                        CircleButton(
                            DowntifyIcons.Back,
                            stringResource(R.string.action_back),
                            onBack,
                            Modifier.padding(start = Spacing.xs),
                            containerColor = scheme.onPrimaryContainer.copy(alpha = TINT_ALPHA),
                            contentColor = scheme.onPrimaryContainer,
                        )
                    },
                    actions = {
                        if (state.kind == CollectionKind.Playlist || state.kind == CollectionKind.Album) {
                            Box {
                                CircleButton(
                                    icon = DowntifyIcons.MoreVert,
                                    contentDescription = "More options",
                                    onClick = { menuExpanded = true },
                                    modifier = Modifier.padding(end = Spacing.xs),
                                    containerColor = scheme.onPrimaryContainer.copy(alpha = TINT_ALPHA),
                                    contentColor = scheme.onPrimaryContainer,
                                )
                                DropdownMenu(
                                    expanded = menuExpanded,
                                    onDismissRequest = { menuExpanded = false },
                                ) {
                                    DropdownMenuItem(
                                        text = { Text("Share") },
                                        onClick = {
                                            menuExpanded = false
                                            onShareCollection()
                                        },
                                    )
                                    if (state.kind == CollectionKind.Playlist && playlistActions != null && state.playlist != null) {
                                        val playlist = state.playlist
                                        DropdownMenuItem(
                                            text = { Text("Suggestions") },
                                            onClick = {
                                                menuExpanded = false
                                                if (state.suggestions.isEmpty() && !state.loadingSuggestions) {
                                                    playlistActions.onLoadSuggestions()
                                                }
                                                scope.launch {
                                                    val target = (state.tracks.size + 1 + (if (state.favoriteError) 1 else 0))
                                                        .coerceAtMost((list.layoutInfo.totalItemsCount - 1).coerceAtLeast(0))
                                                    list.animateScrollToItem(target)
                                                }
                                            },
                                        )
                                        if (playlist.isOwner) {
                                            DropdownMenuItem(
                                                text = { Text(if (playlist.isPublic) "Make Private" else "Make Public") },
                                                onClick = {
                                                    menuExpanded = false
                                                    playlistActions.onToggleVisibility()
                                                },
                                            )
                                            DropdownMenuItem(
                                                text = { Text("Rename") },
                                                onClick = {
                                                    menuExpanded = false
                                                    showRenameDialog = true
                                                },
                                            )
                                        }
                                        DropdownMenuItem(
                                            text = { Text("Clone") },
                                            onClick = {
                                                menuExpanded = false
                                                showCloneDialog = true
                                            },
                                        )
                                        if (playlist.isPublic && !playlist.isOwner) {
                                            DropdownMenuItem(
                                                text = { Text(if (playlist.hidden) "Unhide" else "Hide") },
                                                onClick = {
                                                    menuExpanded = false
                                                    playlistActions.onToggleHidden()
                                                },
                                            )
                                        }
                                        if (playlist.canChangeOwner) {
                                            DropdownMenuItem(
                                                text = { Text("Transfer Ownership") },
                                                onClick = {
                                                    menuExpanded = false
                                                    playlistActions.onLoadUsers()
                                                    showOwnerDialog = true
                                                },
                                            )
                                        }
                                        if (playlist.isOwner || playlist.canEdit) {
                                            DropdownMenuItem(
                                                text = { Text("Delete", color = MaterialTheme.colorScheme.error) },
                                                onClick = {
                                                    menuExpanded = false
                                                    showDeleteDialog = true
                                                },
                                            )
                                        }
                                    } else if (state.kind == CollectionKind.Album) {
                                        DropdownMenuItem(
                                            text = { Text("Add all to queue") },
                                            onClick = {
                                                menuExpanded = false
                                                state.tracks.forEach(trackActions.onAddToQueue)
                                            },
                                        )
                                        if (state.artistId.isNotBlank()) {
                                            DropdownMenuItem(
                                                text = { Text("Go to artist") },
                                                onClick = {
                                                    menuExpanded = false
                                                    onArtist(state.artistId)
                                                },
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = Color.Transparent,
                        scrolledContainerColor = Color.Transparent,
                    ),
                )
            }
        },
    ) { padding ->
        when {
            state.loading -> Box(
                Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                LoadingIndicator()
            }

            state.notFound -> EmptyState(
                icon = DowntifyIcons.Album,
                title = stringResource(R.string.collection_not_found),
                hero = true,
                modifier = Modifier.padding(padding),
            )

            else -> Box(Modifier.fillMaxSize()) {
                LazyColumn(
                    state = list,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(bottom = Spacing.xl + padding.calculateBottomPadding()).plusBottomBars(),
                    verticalArrangement = Arrangement.spacedBy(ListStyle.Separated.gap),
                ) {
                    item(key = "header") {
                        CoverTheme(seedUrl) {
                            Header(
                                state,
                                title,
                                coverUrl,
                                appSurface,
                                onArtist,
                                onPlayOrPause,
                                onShuffle,
                                onToggleOffline,
                            )
                        }
                    }
                    if (state.favoriteError) {
                        item(key = "favorite-error") {
                            Text(
                                stringResource(R.string.playlist_favorite_failed),
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.padding(Spacing.screen),
                            )
                        }
                    }
                    itemsIndexed(state.tracks, key = { i, t -> "$i:${t.id}" }) { index, track ->
                        TrackItem(
                            track = track,
                            onClick = { onPlay(index) },
                            number = if (state.kind == CollectionKind.Album) {
                                track.trackNumber.takeIf { it > 0 } ?: (index + 1)
                            } else {
                                null
                            },
                            coverUrl = covers.track(track.id.takeIf { track.hasCover }, ServerUrls.COVER_SMALL),
                            isCurrent = track.id == state.currentTrackId && state.isCurrentContext,
                            isPlaying = state.isPlaying,
                            isLiked = track.id in state.likedIds,
                            downloaded = track.id in state.offline.downloadedIds,
                            actions = trackActions,
                            showDuration = false,
                            modifier = Modifier.padding(horizontal = Spacing.screen),
                        )
                    }
                    if (state.kind == CollectionKind.Playlist && playlistActions != null) {
                        item(key = "playlist-suggestions") {
                            PlaylistSuggestionsSection(
                                suggestions = state.suggestions,
                                loading = state.loadingSuggestions,
                                addingIds = state.addingSuggestionIds,
                                addedIds = state.addedSuggestionIds,
                                onRefresh = playlistActions.onLoadSuggestions,
                                onPlay = playlistActions.onPlaySuggestion,
                                onAdd = playlistActions.onAddSuggestion,
                            )
                        }
                    }
                            modifier = Modifier.padding(horizontal = Spacing.screen),
                        )
                    }
                    // No navigation bar here: the list clears the system's, unless the mini player under it does.
                    item(key = "system-bar") { Spacer(Modifier.windowInsetsBottomHeight(WindowInsets.navigationBars)) }
                }
                Scrollbar(list)
            }
        }
    }

    if (showCloneDialog && playlistActions != null) {
        var newName by remember { mutableStateOf("${state.title} (Copy)") }
        AlertDialog(
            onDismissRequest = { showCloneDialog = false },
            title = { Text("Clone playlist") },
            text = {
                OutlinedTextField(
                    value = newName,
                    onValueChange = { newName = it },
                    label = { Text("New playlist name") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            },
            confirmButton = {
                TextButton(
                    enabled = newName.isNotBlank(),
                    onClick = {
                        playlistActions.onClone(newName)
                        showCloneDialog = false
                    },
                ) { Text("Clone") }
            },
            dismissButton = {
                TextButton(onClick = { showCloneDialog = false }) { Text(stringResource(R.string.action_cancel)) }
            },
        )
    }

    if (showRenameDialog && playlistActions != null) {
        var newName by remember { mutableStateOf(state.title) }
        AlertDialog(
            onDismissRequest = { showRenameDialog = false },
            title = { Text("Rename playlist") },
            text = {
                OutlinedTextField(
                    value = newName,
                    onValueChange = { newName = it },
                    label = { Text("Playlist name") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            },
            confirmButton = {
                TextButton(
                    enabled = newName.isNotBlank(),
                    onClick = {
                        playlistActions.onRename(newName)
                        showRenameDialog = false
                    },
                ) { Text("Rename") }
            },
            dismissButton = {
                TextButton(onClick = { showRenameDialog = false }) { Text(stringResource(R.string.action_cancel)) }
            },
        )
    }

    if (showDeleteDialog && playlistActions != null) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("Delete playlist?") },
            text = { Text("Delete \"${state.title}\" from the server?") },
            confirmButton = {
                TextButton(
                    onClick = {
                        showDeleteDialog = false
                        playlistActions.onDelete()
                    },
                ) { Text("Delete", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteDialog = false }) { Text(stringResource(R.string.action_cancel)) }
            },
        )
    }

    if (showOwnerDialog && playlistActions != null) {
        AlertDialog(
            onDismissRequest = { showOwnerDialog = false },
            title = { Text("Transfer ownership") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (state.users.isEmpty()) {
                        Text("Loading users...")
                    } else {
                        state.users.forEach { user ->
                            TextButton(
                                onClick = {
                                    playlistActions.onChangeOwner(user.id)
                                    showOwnerDialog = false
                                },
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text(
                                    "${user.displayName.ifBlank { user.username }} (@${user.username})",
                                    modifier = Modifier.fillMaxWidth(),
                                )
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showOwnerDialog = false }) { Text(stringResource(R.string.action_cancel)) }
            },
        )
    }
}

@Composable
private fun PlaylistSuggestionsSection(
    suggestions: List<PlaylistSuggestionItemDto>,
    loading: Boolean,
    addingIds: Set<String>,
    addedIds: Set<String>,
    onRefresh: () -> Unit,
    onPlay: (PlaylistSuggestionItemDto) -> Unit,
    onAdd: (PlaylistSuggestionItemDto) -> Unit,
) {
    val covers = LocalCoverUrls.current
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = Spacing.screen, vertical = Spacing.sm),
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
    ) {
        Column(
            modifier = Modifier.padding(Spacing.md),
            verticalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "Suggested Songs",
                    style = MaterialTheme.typography.titleMedium,
                )
                TextButton(onClick = onRefresh, enabled = !loading) {
                    Text(if (loading) "Loading..." else "Refresh")
                }
            }
            if (loading && suggestions.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(Spacing.md),
                    contentAlignment = Alignment.Center,
                ) {
                    LoadingIndicator()
                }
            } else if (suggestions.isEmpty()) {
                Text(
                    "No song suggestions available yet.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = Spacing.xs),
                )
            } else {
                suggestions.forEach { item ->
                    val itemId = item.displayId.ifBlank { item.displayTitle }
                    val isAdding = addingIds.contains(itemId)
                    val isAdded = addedIds.contains(itemId)
                    val coverUrl = when {
                        item.displayCover.startsWith("http") -> item.displayCover
                        item.trackId.isNotBlank() -> covers.track(item.trackId, ServerUrls.COVER_SMALL)
                        item.displayCover.isNotBlank() -> item.displayCover
                        else -> null
                    }

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                    ) {
                        Box(
                            modifier = Modifier
                                .size(48.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .clickable { onPlay(item) },
                            contentAlignment = Alignment.Center,
                        ) {
                            Artwork(
                                url = coverUrl,
                                contentDescription = null,
                                shape = RoundedCornerShape(8.dp),
                                placeholderIcon = DowntifyIcons.Song,
                                modifier = Modifier.size(48.dp),
                            )
                            Box(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .background(Color.Black.copy(alpha = 0.35f)),
                                contentAlignment = Alignment.Center,
                            ) {
                                Icon(
                                    painter = painterResource(DowntifyIcons.Play),
                                    contentDescription = "Play ${item.displayTitle}",
                                    tint = Color.White,
                                    modifier = Modifier.size(24.dp),
                                )
                            }
                        }

                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .clickable { onPlay(item) },
                        ) {
                            Text(
                                item.displayTitle,
                                style = MaterialTheme.typography.bodyMedium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                item.displayArtist,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }

                        when {
                            isAdded -> {
                                TextButton(
                                    onClick = {},
                                    enabled = false,
                                ) {
                                    Icon(
                                        painter = painterResource(DowntifyIcons.CheckCircle),
                                        contentDescription = null,
                                        modifier = Modifier.size(16.dp),
                                    )
                                    Spacer(Modifier.width(4.dp))
                                    Text("Added")
                                }
                            }
                            isAdding -> {
                                TextButton(
                                    onClick = {},
                                    enabled = false,
                                ) {
                                    Text("Adding...")
                                }
                            }
                            else -> {
                                TextButton(
                                    onClick = { onAdd(item) },
                                ) {
                                    Text("+ Add")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Suppress("LongParameterList")
@Composable
private fun Header(
    state: CollectionUiState,
    title: String,
    coverUrl: String?,
    appSurface: Color,
    onArtist: (String) -> Unit,
    onPlayOrPause: () -> Unit,
    onShuffle: () -> Unit,
    onToggleOffline: () -> Unit,
) {
    val scheme = MaterialTheme.colorScheme
    Column(
        Modifier
            .fillMaxWidth()
            .background(Brush.verticalGradient(listOf(scheme.primaryContainer, appSurface)))
            .statusBarsPadding()
            .padding(top = 56.dp)
            .padding(horizontal = Spacing.xl, vertical = Spacing.xs),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(Spacing.lg),
    ) {
        Artwork(
            url = coverUrl,
            contentDescription = null,
            shape = DowntifyShape.Artwork,
            placeholderIcon = if (state.kind ==
                CollectionKind.Liked
            ) {
                DowntifyIcons.FavoriteFilled
            } else {
                DowntifyIcons.Album
            },
            tone = if (state.kind == CollectionKind.Liked) ArtworkTone.Primary else ArtworkTone.Neutral,
            modifier = Modifier.size(COVER_SIZE),
        )
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            Text(
                title,
                style = MaterialTheme.typography.headlineMediumEmphasized,
                color = scheme.onPrimaryContainer,
                textAlign = TextAlign.Center,
                modifier = Modifier.semantics { heading() },
            )
            if (state.artist.isNotBlank()) {
                Text(
                    state.artist,
                    style = MaterialTheme.typography.titleMedium,
                    color = scheme.onPrimaryContainer,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.clickable(enabled = state.artistId.isNotEmpty()) { onArtist(state.artistId) },
                )
            }
            Details(state)
        }
        Actions(state, title, onPlayOrPause, onShuffle, onToggleOffline)
    }
}

/** Year, songs and length as small tags: they wrap whole, never mid-value. */
@Composable
private fun Details(state: CollectionUiState) {
    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(Spacing.sm, Alignment.CenterHorizontally),
        verticalArrangement = Arrangement.spacedBy(Spacing.sm),
    ) {
        if (state.year.isNotBlank()) Tag(state.year, small = true, tone = TagTone.OnColor)
        state.playlist?.takeIf { it.owner.isNotBlank() }?.let { pl ->
            Tag("by ${pl.owner}", small = true, tone = TagTone.OnColor)
        }
        Tag(songsCount(state.tracks.size), small = true, tone = TagTone.OnColor)
    }
}

@OptIn(ExperimentalMaterial3ExpressiveApi::class)
@Composable
private fun Actions(
    state: CollectionUiState,
    title: String,
    onPlayOrPause: () -> Unit,
    onShuffle: () -> Unit,
    onToggleOffline: () -> Unit,
) {
    val playing = state.isCurrentContext && state.isPlaying
    val scheme = MaterialTheme.colorScheme
    var confirmRemove by remember { mutableStateOf(false) }
    Row(
        Modifier
            .fillMaxWidth()
            .padding(bottom = Spacing.sm),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
    ) {
        OfflineChip(
            offline = state.offline,
            enabled = state.tracks.isNotEmpty() || state.offline.kept,
            onClick = { if (state.offline.kept) confirmRemove = true else onToggleOffline() },
        )
        Spacer(Modifier.weight(1f))
        FilledIconButton(
            onClick = onPlayOrPause,
            enabled = state.tracks.isNotEmpty(),
            shapes = IconButtonShapes(shape = DowntifyShape.Fab, pressedShape = RoundedCornerShape(16.dp)),
            colors = IconButtonDefaults.filledIconButtonColors(
                containerColor = scheme.primary,
                contentColor = scheme.onPrimary,
            ),
            modifier = Modifier.size(64.dp),
        ) {
            Icon(
                painterResource(if (playing) DowntifyIcons.Pause else DowntifyIcons.Play),
                contentDescription = stringResource(
                    if (playing) R.string.collection_pause else R.string.collection_play,
                    title,
                ),
                modifier = Modifier.size(32.dp),
            )
        }
    }
    if (confirmRemove) {
        AlertDialog(
            onDismissRequest = { confirmRemove = false },
            title = { Text(stringResource(R.string.collection_remove_title)) },
            text = { Text(stringResource(R.string.collection_remove_message, title)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmRemove = false
                        onToggleOffline()
                    },
                ) { Text(stringResource(R.string.collection_remove_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { confirmRemove = false }) { Text(stringResource(R.string.action_cancel)) }
            },
        )
    }
}

/** "Download", then "Downloading 3 of 10", then "On this phone" — the design's offline toggle. */
@Composable
private fun OfflineChip(offline: CollectionOffline, enabled: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected = offline.kept,
        onClick = onClick,
        enabled = enabled,
        label = {
            Text(
                when {
                    !offline.kept -> stringResource(R.string.collection_download)
                    offline.isComplete -> stringResource(R.string.collection_on_phone)
                    else -> stringResource(R.string.collection_downloading, offline.downloaded, offline.total)
                },
            )
        },
        leadingIcon = {
            Icon(
                painterResource(if (offline.isComplete) DowntifyIcons.CheckCircle else DowntifyIcons.Downloads),
                contentDescription = null,
                tint = if (offline.kept) MaterialTheme.colorScheme.primary else LocalContentColor.current,
                modifier = Modifier.size(FilterChipDefaults.IconSize),
            )
        },
        shape = CircleShape,
        modifier = Modifier.heightIn(min = 40.dp),
    )
}

private val COVER_SIZE = 232.dp
private const val TINT_ALPHA = 0.12f

@PhonePreviews
@Composable
private fun AlbumPreview() {
    val album = PreviewData.albums.first()
    DowntifyTheme {
        CollectionScreen(
            state = CollectionUiState(
                loading = false,
                title = album.title,
                artist = album.artist,
                artistId = album.artistId,
                year = album.year,
                tracks = album.tracks,
                currentTrackId = "t2",
                isPlaying = true,
                isCurrentContext = true,
            ),
            onBack = {},
            onArtist = {},
            onPlay = {},
            onPlayOrPause = {},
            onShuffle = {},
            modifier = Modifier.statusBarsPadding(),
        )
    }
}
