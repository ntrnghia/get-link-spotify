"""Data models for ZingMP3-Spotify sync."""

from dataclasses import dataclass, field, asdict


@dataclass
class SyncResult:
    """Result of matching a ZingMP3 song with Spotify."""
    rank: int
    song_name: str
    artists: str
    duration: str
    zing_url: str = ""
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
        return bool(self.spotify_url)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_song_and_spotify(cls, song: dict, spotify_result: dict | None) -> "SyncResult":
        result = cls(
            rank=song["position"], song_name=song["name"],
            artists=song["artists"], duration=song["duration"],
            zing_url=song.get("url", ""),
        )
        if spotify_result:
            for key in ("spotify_name", "spotify_artist", "spotify_album", 
                       "spotify_duration", "spotify_url", "popularity", 
                       "match_score", "track_uri"):
                setattr(result, key, spotify_result.get(key, getattr(result, key)))
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
        return (self.songs_found / self.total_songs * 100) if self.total_songs else 0.0


@dataclass
class SyncOutput:
    """Complete output from a chart sync operation."""
    results: list[SyncResult] = field(default_factory=list)
    stats: SyncStats = field(default_factory=SyncStats)
    track_uris: list[str] = field(default_factory=list)

    @property
    def found_count(self) -> int:
        return sum(1 for r in self.results if r.found)
