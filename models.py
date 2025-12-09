"""
Data models for ZingMP3-Spotify sync.
Type-safe dataclasses for results and configurations.
"""

from dataclasses import dataclass, field


@dataclass
class SyncResult:
    """Result of matching a ZingMP3 song with Spotify."""

    # ZingMP3 fields
    rank: int
    song_name: str
    artists: str
    duration: str
    zing_url: str = ""

    # Spotify fields (empty if not found)
    spotify_name: str = ""
    spotify_artist: str = ""
    spotify_album: str = ""
    spotify_duration: str = ""
    spotify_url: str = ""
    popularity: int = 0
    match_score: float = 0.0
    track_uri: str = ""

    @property
    def found(self) -> bool:
        """Whether the song was found on Spotify."""
        return bool(self.spotify_url)

    def to_dict(self) -> dict:
        """Convert to dict for Excel export."""
        return {
            "rank": self.rank,
            "song_name": self.song_name,
            "artists": self.artists,
            "duration": self.duration,
            "zing_url": self.zing_url,
            "spotify_name": self.spotify_name,
            "spotify_artist": self.spotify_artist,
            "spotify_album": self.spotify_album,
            "spotify_duration": self.spotify_duration,
            "spotify_url": self.spotify_url,
            "popularity": self.popularity,
            "match_score": self.match_score,
            "track_uri": self.track_uri,
        }

    @classmethod
    def from_song_and_spotify(
        cls, song: dict, spotify_result: dict | None
    ) -> "SyncResult":
        """Create SyncResult from ZingMP3 song dict and Spotify search result."""
        result = cls(
            rank=song["position"],
            song_name=song["name"],
            artists=song["artists"],
            duration=song["duration"],
            zing_url=song.get("url", ""),
        )

        if spotify_result:
            result.spotify_name = spotify_result["spotify_name"]
            result.spotify_artist = spotify_result["spotify_artist"]
            result.spotify_album = spotify_result["spotify_album"]
            result.spotify_duration = spotify_result["spotify_duration"]
            result.spotify_url = spotify_result["spotify_url"]
            result.popularity = spotify_result["popularity"]
            result.match_score = spotify_result["match_score"]
            result.track_uri = spotify_result["track_uri"]

        return result


@dataclass
class SyncStats:
    """Statistics from a sync operation."""

    total_songs: int = 0
    songs_found: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def found_percentage(self) -> float:
        """Percentage of songs found on Spotify."""
        if self.total_songs == 0:
            return 0.0
        return (self.songs_found / self.total_songs) * 100


@dataclass
class SyncOutput:
    """Complete output from a chart sync operation."""

    results: list[SyncResult] = field(default_factory=list)
    stats: SyncStats = field(default_factory=SyncStats)
    track_uris: list[str] = field(default_factory=list)

    @property
    def found_count(self) -> int:
        """Number of songs found on Spotify."""
        return sum(1 for r in self.results if r.found)
