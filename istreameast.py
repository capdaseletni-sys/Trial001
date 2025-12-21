import base64
import re

from selectolax.parser import HTMLParser

from .caching import Cache
from .config import Time, leagues
from .logger import get_logger
from .webwork import network

__all__ = [
    "Cache",
    "Time",
    "get_logger",
    "leagues",
    "network",
]

import json
from pathlib import Path

from .config import Time


class Cache:
    def __init__(self, file: str, exp: int | float) -> None:
        self.file = Path(__file__).parent.parent / "caches" / file

        self.exp = exp

        self.now_ts = Time.now().timestamp()

    def is_fresh(self, entry: dict) -> bool:
        ts: float | int = entry.get("timestamp", Time.default_8())

        dt_ts = Time.clean(Time.from_ts(ts)).timestamp()

        return self.now_ts - dt_ts < self.exp

    def write(self, data: dict) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)

        self.file.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def load(
        self,
        per_entry: bool = True,
        index: int | None = None,
    ) -> dict[str, dict[str, str | float]]:

        try:
            data: dict = json.loads(self.file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

        if per_entry:
            return {k: v for k, v in data.items() if self.is_fresh(v)}

        if index:
            ts: float | int = data[index].get("timestamp", Time.default_8())

        else:
            ts: float | int = data.get("timestamp", Time.default_8())

        dt_ts = Time.clean(Time.from_ts(ts)).timestamp()

        return data if self.is_fresh({"timestamp": dt_ts}) else {}


__all__ = ["Cache"]

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytz


class Time(datetime):
    ZONES = {
        "CET": pytz.timezone("Europe/Berlin"),
        "ET": pytz.timezone("America/New_York"),
        "PST": pytz.timezone("America/Los_Angeles"),
        "UTC": timezone.utc,
    }

    ZONES["EDT"] = ZONES["EST"] = ZONES["ET"]

    TZ = ZONES["ET"]

    @classmethod
    def now(cls) -> "Time":
        return cls.from_ts(datetime.now(cls.TZ).timestamp())

    @classmethod
    def from_ts(cls, ts: int | float) -> "Time":
        return cls.fromtimestamp(ts, tz=cls.TZ)

    @classmethod
    def default_8(cls) -> float:
        return (
            cls.now()
            .replace(hour=8, minute=0, second=0, microsecond=0, tzinfo=cls.TZ)
            .timestamp()
        )

    def delta(self, **kwargs) -> "Time":
        return self.from_ts((self + timedelta(**kwargs)).timestamp())

    def clean(self) -> "Time":
        return self.__class__.fromtimestamp(
            self.replace(second=0, microsecond=0).timestamp(),
            tz=self.TZ,
        )

    def to_tz(self, tzone: str) -> "Time":
        dt = self.astimezone(self.ZONES[tzone])

        return self.__class__.fromtimestamp(dt.timestamp(), tz=self.ZONES[tzone])

    @classmethod
    def _to_class_tz(cls, dt) -> "Time":
        dt = dt.astimezone(cls.TZ)

        return cls.fromtimestamp(dt.timestamp(), tz=cls.TZ)

    @classmethod
    def from_only_time(cls, s: str, d: date, timezone: str) -> "Time":
        hour, minute = map(int, s.split(":"))

        dt = datetime(
            2000,
            1,
            1,
            hour,
            minute,
            tzinfo=cls.ZONES.get(timezone, cls.TZ),
        )

        dt = dt.astimezone(cls.TZ)

        dt = datetime.combine(d, dt.timetz())

        return cls.fromtimestamp(dt.timestamp(), tz=cls.TZ)

    @classmethod
    def from_str(
        cls,
        s: str,
        fmt: str | None = None,
        timezone: str | None = None,
    ) -> "Time":
        tz = cls.ZONES.get(timezone, cls.TZ)

        if fmt:
            dt = datetime.strptime(s, fmt)

            dt = tz.localize(dt)

        else:
            formats = [
                "%B %d, %Y %I:%M %p",
                "%B %d, %Y %I:%M:%S %p",
                "%m/%d/%Y %I:%M %p",
                "%B %d, %Y %H:%M",
                "%B %d, %Y %H:%M:%S",
                "%Y-%m-%d",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M %p",
                "%Y-%m-%d %I:%M %p",
                "%Y/%m/%d %H:%M",
                "%Y/%m/%d %H:%M:%S",
                "%m/%d/%Y %H:%M",
                "%m/%d/%Y %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y/%m/%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%a, %d %b %Y %H:%M:%S %z",
            ]

            for frmt in formats:
                try:
                    dt = datetime.strptime(s, frmt)
                    break
                except ValueError:
                    continue
            else:
                return cls.from_ts(Time.default_8())

            if not dt.tzinfo:
                dt = (
                    tz.localize(dt)
                    if hasattr(tz, "localize")
                    else dt.replace(tzinfo=tz)
                )

        return cls._to_class_tz(dt)


class Leagues:
    live_img = "https://i.gyazo.com/978f2eb4a199ca5b56b447aded0cb9e3.png"

    def __init__(self) -> None:
        self.data = json.loads(
            (Path(__file__).parent / "leagues.json").read_text(encoding="utf-8")
        )

    def teams(self, league: str) -> list[str]:
        return self.data["teams"].get(league, [])

    def info(self, name: str) -> tuple[str | None, str]:
        name = name.upper()

        if match := next(
            (
                (tvg_id, league_data.get("logo"))
                for tvg_id, leagues in self.data["leagues"].items()
                for league_entry in leagues
                for league_name, league_data in league_entry.items()
                if name == league_name or name in league_data.get("names", [])
            ),
            None,
        ):
            tvg_id, logo = match

            return (tvg_id, logo or self.live_img)

        return (None, self.live_img)

    def is_valid(
        self,
        event: str,
        league: str,
    ) -> bool:

        pattern = re.compile(r"\s+(?:-|vs\.?|at|@)\s+", flags=re.IGNORECASE)

        if pattern.search(event):
            t1, t2 = re.split(pattern, event)

            return any(t in self.teams(league) for t in (t1.strip(), t2.strip()))

        return event.lower() in {
            "nfl redzone",
            "redzone",
            "red zone",
            "college gameday",
        }

    def get_tvg_info(
        self,
        sport: str,
        event: str,
    ) -> tuple[str | None, str]:

        match sport:
            case "American Football" | "NFL":
                return (
                    self.info("NFL")
                    if self.is_valid(event, "NFL")
                    else self.info("NCAA")
                )

            case "Basketball" | "NBA":
                if self.is_valid(event, "NBA"):
                    return self.info("NBA")

                elif self.is_valid(event, "WNBA"):
                    return self.info("WNBA")

                else:
                    return self.info("Basketball")

            case "Ice Hockey" | "Hockey":
                return self.info("NHL")

            case _:
                return self.info(sport)


leagues = Leagues()

__all__ = ["leagues", "Time"]

{
  "leagues": {
    "Basketball.Dummy.us": [
      {
        "BASKETBALL": {
          "logo": "https://1000logos.net/wp-content/uploads/2024/04/Basketball-Emoji-1536x864.png",
          "names": []
        }
      },
      {
        "EUROLEAGUE": {
          "logo": "https://www.euroleaguebasketball.net/images/logo-default.png",
          "names": ["EUROLEAGUE BASKETBALL"]
        }
      }
    ],
    "Golf.Dummy.us": [
      {
        "GOLF": {
          "logo": "https://i.gyazo.com/14a883f22796f631e6f97c34dbeb6ada.png",
          "names": []
        }
      },
      {
        "PGA": {
          "logo": "https://1000logos.net/wp-content/uploads/2024/10/PGA-Tour-Logo-500x281.png",
          "names": ["PGA TOUR"]
        }
      }
    ],
    "MLB.Baseball.Dummy.us": [
      {
        "MLB": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/mlb.png",
          "names": ["BASEBALL", "MAJOR LEAGUE BASEBALL", "MLB PLAYOFFS"]
        }
      }
    ],
    "NBA.Basketball.Dummy.us": [
      {
        "NBA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/nba.png",
          "names": [
            "NATIONAL BASKETBALL ASSOCIATION",
            "NBA BASKETBALL",
            "NBA CUP",
            "NBA PLAYOFFS",
            "NBA PRESEASON"
          ]
        }
      }
    ],
    "NCAA.Sports.Dummy.us": [
      {
        "NCAA": {
          "logo": "https://1000logos.net/wp-content/uploads/2021/12/NCAA-Logo-500x281.png",
          "names": [
            "CBB",
            "CFB",
            "CFB PLAYOFFS",
            "CFP",
            "COLLEGE BASKETBALL",
            "COLLEGE FOOTBALL",
            "MARCH MADNESS",
            "NCAA - BASKETBALL",
            "NCAA - FOOTBALL",
            "NCAA AMERICAN FOOTBALL",
            "NCAA BASKETBALL",
            "NCAA FOOTBALL",
            "NCAA MEN",
            "NCAA SPORTS",
            "NCAA WOMEN",
            "NCAAB",
            "NCAAB D",
            "NCAAB D-I",
            "NCAAF",
            "NCAAF D-I",
            "NCAAM",
            "NCAAW"
          ]
        }
      }
    ],
    "NFL.Dummy.us": [
      {
        "NFL": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/nfl.png",
          "names": [
            "AMERICAN FOOTBALL",
            "NATIONAL FOOTBALL LEAGUE",
            "NFL PLAYOFFS",
            "NFL PRESEASON",
            "USA NFL"
          ]
        }
      }
    ],
    "NHL.Hockey.Dummy.us": [
      {
        "NHL": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/nhl.png",
          "names": [
            "HOCKEY",
            "NATIONAL HOCKEY LEAGUE",
            "NHL HOCKEY",
            "NHL PLAYOFFS",
            "NHL PRESEASON"
          ]
        }
      }
    ],
    "PPV.EVENTS.Dummy.us": [
      {
        "PAY PER VIEW": {
          "logo": null,
          "names": ["PAY-PER-VIEW", "PAYPERVIEW", "PPV"]
        }
      },
      {
        "WRESTLING": {
          "logo": null,
          "names": ["AEW", "WWE"]
        }
      }
    ],
    "Racing.Dummy.us": [
      {
        "F1": {
          "logo": "https://1000logos.net/wp-content/uploads/2021/06/F1-logo-500x281.png",
          "names": [
            "FORMULA 1",
            "FORMULA 1 GP",
            "FORMULA ONE",
            "FORMULA ONE GP"
          ]
        }
      },
      {
        "MOTO GP": {
          "logo": "https://1000logos.net/wp-content/uploads/2021/03/MotoGP-Logo-500x281.png",
          "names": ["MOTOGP"]
        }
      },
      {
        "RACING": {
          "logo": null,
          "names": []
        }
      }
    ],
    "Soccer.Dummy.us": [
      {
        "2. BUNDESLIGA": {
          "logo": "https://i.gyazo.com/6c343e57acf501f4df3502d7ec646897.png",
          "names": ["GERMAN 2. BUNDESLIGA"]
        }
      },
      {
        "3. LIGA": {
          "logo": "https://i.gyazo.com/9f4f2e8370377b6214b4103003196de7.png",
          "names": []
        }
      },
      {
        "AFC CHAMPIONS LEAGUE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2200.png&scale=crop&cquality=40&location=origin&w=500&h=500",
          "names": [
            "ACL",
            "ACL ELITE",
            "AFC CHAMPIONS LEAGUE ELITE",
            "ASIAN CHAMPIONS LEAGUE"
          ]
        }
      },
      {
        "AFRICA CUP OF NATIONS": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/76.png",
          "names": ["AFCON"]
        }
      },
      {
        "AUSTRIA 2 LIGA": {
          "logo": "https://i.gyazo.com/5d1464502b841fef6e5d78c8b0764b52.png",
          "names": ["ADMIRAL 2. LIGA"]
        }
      },
      {
        "AUSTRIA BUNDESLIGA": {
          "logo": "https://i.gyazo.com/83d851fb1110f1e395690403f9cf01bb.webp",
          "names": ["ADMIRAL BUNDESLIGA", "FEDERAL LEAGUE"]
        }
      },
      {
        "BUNDESLIGA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/10.png",
          "names": ["BUNDESLIG", "GERMAN BUNDESLIGA"]
        }
      },
      {
        "CAF CHAMPIONS LEAGUE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2391.png",
          "names": []
        }
      },
      {
        "CANADIAN PREMIER LEAGUE": {
          "logo": "https://i.gyazo.com/f61986e2ccfbf88f7d753b4e7f2c9fdc.png",
          "names": ["CANPL", "CPL"]
        }
      },
      {
        "CHAMPIONSHIP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/24.png",
          "names": [
            "ENGLISH CHAMPIONSHIP",
            "ENGLISH FOOTBALL LEAGUE CHAMPIONSHIP",
            "ENGLISH LEAGUE CHAMPIONSHIP",
            "SKY BET CHAMPIONSHIP"
          ]
        }
      },
      {
        "CONCACAF CENTRAL AMERICAN CUP": {
          "logo": "https://b.fssta.com/uploads/application/soccer/competition-logos/CONCACAFCentralAmericanCup.png",
          "names": ["COPA CENTROAMERICANA DE CONCACAF"]
        }
      },
      {
        "CONCACAF CHAMPIONS LEAGUE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2298.png",
          "names": ["CONCACAF CHAMPIONS CUP"]
        }
      },
      {
        "CONCACAF GOLD CUP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/59.png",
          "names": ["COPA ORO CONCACAF"]
        }
      },
      {
        "CONCACAF W CHAMPIONS CUP": {
          "logo": "https://i.gyazo.com/c1caff728e9a32711254b98d008194b2.png",
          "names": []
        }
      },
      {
        "CONCACAF W CHAMPIONSHIP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/18969.png",
          "names": []
        }
      },
      {
        "COPA AMÉRICA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/83.png",
          "names": [
            "CONMEBOL COPA AMERICA",
            "COPA AMERICA",
            "COPA LIBERTADORES DE AMÉRICA",
            "SOUTH AMERICAN FOOTBALL CHAMPIONSHIP"
          ]
        }
      },
      {
        "COPA DEL REY": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/80.png",
          "names": [
            "KING'S CUP",
            "KINGS CUP",
            "LA COPA",
            "SPAIN COPA DEL REY",
            "SPANISH COPA DEL REY",
            "SPANISH CUP"
          ]
        }
      },
      {
        "COPA LIBERTADORES": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/58.png",
          "names": [
            "CONMEBOL LIBERTADORES",
            "COPA LIBERTADORES DE AMERICA",
            "COPA LIBERTADORES DE AMÉRICA",
            "LIBERTADORES"
          ]
        }
      },
      {
        "COPA SUDAMERICANA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/1208.png",
          "names": ["CONMEBOL SUDAMERICANA", "COPA CONMEBOL SUDAMERICANA"]
        }
      },
      {
        "COPPA ITALIA": {
          "logo": "https://i.gyazo.com/8fd7660cca8f8b690f50979b72b295c3.png",
          "names": ["ITALIAN CUP"]
        }
      },
      {
        "COUPE DE FRANCE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/182.png",
          "names": ["FRANCE CUP", "FRENCH CUP"]
        }
      },
      {
        "EFL": {
          "logo": "https://i.gyazo.com/c8842fbcb2eeb6a53bc69fa6055b8b5d.png",
          "names": [
            "CARABAO CUP",
            "EFL CUP",
            "ENGLISH CARABAO CUP",
            "ENGLISH FOOTBALL LEAGUE CUP",
            "LEAGUE CUP"
          ]
        }
      },
      {
        "EFL LEAGUE ONE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/25.png",
          "names": [
            "ENGLISH FOOTBALL LEAGUE ONE",
            "LEAGUE ONE",
            "SKY BET LEAGUE ONE"
          ]
        }
      },
      {
        "EFL LEAGUE TWO": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/26.png",
          "names": [
            "ENGLISH FOOTBALL LEAGUE TWO",
            "LEAGUE TWO",
            "SKY BET LEAGUE TWO"
          ]
        }
      },
      {
        "EKSTRAKLASA": {
          "logo": "https://i.gyazo.com/362e31efdd0dad03b00858f4fb0901b5.png",
          "names": ["PKO BANK POLSKI EKSTRAKLASA", "POLAND EKSTRAKLASA"]
        }
      },
      {
        "EREDIVISIE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/11.png",
          "names": [
            "DUTCH EERSTE EREDIVISIE",
            "DUTCH EREDIVISIE",
            "NETHERLANDS EREDIVISIE",
            "VRIENDENLOTERIJ EREDIVISIE"
          ]
        }
      },
      {
        "FA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/40.png&w=500&h=500",
          "names": [
            "EMIRATES FA CUP",
            "ENGLISH FA CUP",
            "FA CUP",
            "FOOTBALL ASSOCIATION CHALLENGE CUP"
          ]
        }
      },
      {
        "FIFA CLUB WORLD CUP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/1932.png",
          "names": ["FIFA CWC"]
        }
      },
      {
        "FIFA WORLD CUP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/4.png",
          "names": ["FIFA WC", "WC"]
        }
      },
      {
        "FIFA'S WOMEN WORLD CUP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/60.png",
          "names": ["FIFA WOMEN WC"]
        }
      },
      {
        "FOOTBALL": {
          "logo": "https://i.gyazo.com/1c4aa937f5ea01b0f29bb27adb59884c.png",
          "names": []
        }
      },
      {
        "FRAUEN BUNDESLIGA": {
          "logo": "https://i.gyazo.com/d13d4c0330be96801aa4b2d8b83d3a8f.png",
          "names": ["GOOGLE PIXEL FRAUEN-BUNDESLIGA", "WOMEN'S FEDERAL LEAGUE"]
        }
      },
      {
        "GREECE CUP": {
          "logo": "https://i.gyazo.com/f80306df9b94a90f991b3cce386dc2b5.png",
          "names": ["BETSSON GREECE UP", "GREEK CUP", "GREEK FOOTBALL CUP"]
        }
      },
      {
        "J1 LEAGUE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2199.png",
          "names": ["J.LEAGUE", "JAPANESE J.LEAGUE", "MEIJI YASUDA J1 LEAGUE"]
        }
      },
      {
        "K LEAGUE 1": {
          "logo": "https://i.gyazo.com/721eba6c954e2015d999ead7a0bd5c69.png",
          "names": []
        }
      },
      {
        "LA LIGA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/15.png",
          "names": [
            "CAMPEONATO NACIONAL DE LIGA DE PRIMERA DIVISION",
            "CAMPEONATO NACIONAL DE LIGA DE PRIMERA DIVISIÓN",
            "LA-LIGA",
            "LALIGA",
            "PRIMERA DIVISION",
            "PRIMERA DIVISIÓN",
            "SPANISH LA LIGA",
            "SPANISH LALIGA"
          ]
        }
      },
      {
        "LA LIGA 2": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/107.png",
          "names": [
            "CAMPEONATO NACIONAL DE LIGA DE SEGUNDA DIVISION",
            "CAMPEONATO NACIONAL DE LIGA DE SEGUNDA DIVISIÓN",
            "LALIGA 2",
            "SEGUNDA DIVISION",
            "SEGUNDA DIVISIÓN",
            "SPAIN SEGUNDA DIVISION",
            "SPANISH LA LIGA 2",
            "SPANISH LALIGA 2",
            "SPANISH SEGUNDA LIGA"
          ]
        }
      },
      {
        "LA PRIMERA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2244.png",
          "names": [
            "LA LIGA MAYOR",
            "PRIMERA DIVISION DE FUTBOL PROFESIONAL DE EL SALVADOR",
            "PRIMERA DIVISIÓN DE EL SALVADOR",
            "PRIMERA DIVISIÓN DE FÚTBOL PROFESIONAL DE EL SALVADOR",
            "SALVADORAN PRIMERA DIVISION"
          ]
        }
      },
      {
        "LEAGUES CUP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2410.png",
          "names": []
        }
      },
      {
        "LIGA DE EXPANSIÓN MX": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2306.png",
          "names": ["LIGA BBVA EXPANSIÓN MX"]
        }
      },
      {
        "LIGA FPD": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2245.png",
          "names": [
            "COSTA RICAN PRIMERA DIVISION",
            "LIGA DE FUTBOL DE PRIMERA DIVISION",
            "LIGA DE FÚTBOL DE PRIMERA DIVISIÓN",
            "LIGA PROMERICA",
            "PRIMERA DIVISION OF COSTA RICA",
            "PRIMERA DIVISIÓN OF COSTA RICA"
          ]
        }
      },
      {
        "LIGA GUATE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2248.png",
          "names": [
            "LIGA GUATE BANRURAL",
            "LIGA NACIONAL",
            "LIGA NACIONAL DE FUTBOL DE GUATEMALA",
            "LIGA NACIONAL DE FÚTBOL DE GUATEMALA"
          ]
        }
      },
      {
        "LIGA HONDUBET": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2247.png",
          "names": [
            "HONDURAN LIGA NACIONAL",
            "LIGA NACIONAL DE FUTBOL PROFESIONAL DE HONDURAS",
            "LIGA NACIONAL DE FÚTBOL PROFESIONAL DE HONDURAS"
          ]
        }
      },
      {
        "LIGA I": {
          "logo": "https://i.gyazo.com/3fd4b38d5263ca391e45850eb58d11e6.png",
          "names": [
            "ROMANIA LIGA 1",
            "ROMANIA LIGA I",
            "ROMANIAN LIGA 1",
            "ROMANIAN LIGA I",
            "SUPERLIGA"
          ]
        }
      },
      {
        "LIGA MX": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/22.png",
          "names": [
            "LIGA BBVA MX",
            "MEXICAN LIGA BBVA MX",
            "MEXICO LIGA MX",
            "PRIMERA DIVISION DE MEXICO",
            "PRIMERA DIVISIÓN DE MÉXICO"
          ]
        }
      },
      {
        "LIGA MX FEMENIL": {
          "logo": "https://i.gyazo.com/ee0e1ba5ea748951b7ec7f46fb411c4f.png",
          "names": ["LIGA BBVA MX FEMENIL", "MEXICO WOMEN LIGA MX"]
        }
      },
      {
        "LIGA PROFESIONAL ARGENTINA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/1.png",
          "names": [
            "ARGENTINE PRIMERA DIVISION",
            "ARGENTINE PRIMERA DIVISIÓN",
            "LIGA PROFESIONAL DE FUTBOL",
            "LIGA PROFESIONAL DE FÚTBOL",
            "PRIMERA DIVISION",
            "PRIMERA DIVISIÓN",
            "TORNEO BETANO"
          ]
        }
      },
      {
        "LIGUE 1": {
          "logo": "https://ligue1.com/images/Logo_Ligue_1.webp",
          "names": ["FRANCE LIGUE 1", "FRENCH LIGUE 1"]
        }
      },
      {
        "LIGUE 2": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/96.png",
          "names": ["FRANCE LIGUE 2", "FRENCH LIGUE 2"]
        }
      },
      {
        "MLS": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/19.png",
          "names": ["MAJOR LEAGUE SOCCER"]
        }
      },
      {
        "NORTHERN SUPER LEAGUE": {
          "logo": "https://i.gyazo.com/042f5bf51ab721bede2d9b56ce1818ae.png",
          "names": ["NSL"]
        }
      },
      {
        "NWSL": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2323.png",
          "names": ["NATIONAL WOMEN'S SOCCER LEAGUE", "NWSL WOMEN"]
        }
      },
      {
        "NWSL CHALLENGE CUP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2445.png",
          "names": []
        }
      },
      {
        "PREMIER LEAGUE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/23.png",
          "names": ["ENGLISH PREMIER LEAGUE", "EPL"]
        }
      },
      {
        "PRIMEIRA LIGA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/14.png",
          "names": ["LIGA PORTUGAL", "PORTUGUESE PRIMEIRA LIGA"]
        }
      },
      {
        "PRIMERA A": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/1543.png",
          "names": ["COLOMBIA PRIMERA A", "COLOMBIAN PRIMERA A"]
        }
      },
      {
        "PRIMERA B": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2295.png",
          "names": ["COLOMBIA PRIMERA B", "COLOMBIAN PRIMERA B"]
        }
      },
      {
        "SCOTTISH PREMIERSHIP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/45.png",
          "names": ["PREMIERSHIP", "SPFL"]
        }
      },
      {
        "SERBIA SUPERLIGA": {
          "logo": "https://i.gyazo.com/0992f078dcacfef489477fc7bb1f5220.webp",
          "names": ["MOZZART SUPERLIGA", "SERBIAN SUPER LEAGUE"]
        }
      },
      {
        "SERIE A": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/12.png",
          "names": ["ITALIAN SERIE A", "ITALY SERIE A", "SERIE-A"]
        }
      },
      {
        "SERIE B": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/99.png",
          "names": ["ITALIAN SERIE B", "ITALY SERIE B", "SERIE-B"]
        }
      },
      {
        "SOCCER": {
          "logo": "https://i.gyazo.com/1c4aa937f5ea01b0f29bb27adb59884c.png",
          "names": []
        }
      },
      {
        "SUPER LEAGUE GREECE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/98.png",
          "names": [
            "A1 ETHNIKI KATIGORIA",
            "GREECE SUPER LEAGUE",
            "GREEK SUPER LEAGUE",
            "SUPER LEAGUE 1"
          ]
        }
      },
      {
        "SÜPER LIG": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/18.png",
          "names": [
            "SUPER LIG",
            "SUPERLIG",
            "SÜPERLIG",
            "TURKEY SUPER LIG",
            "TURKISH SUPER LIG"
          ]
        }
      },
      {
        "TURKEY 1 LIG": {
          "logo": "https://i.gyazo.com/730673f84223a85c9b9ae66123907bba.png",
          "names": ["TFF 1. LIG", "TRENDYOL 1. LIG"]
        }
      },
      {
        "U.S. OPEN CUP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/69.png",
          "names": ["LAMAR HUNT U.S. OPEN CUP", "US OPEN CUP", "USOC"]
        }
      },
      {
        "UEFA CHAMPIONS LEAGUE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2.png",
          "names": ["CHAMPIONS LEAGUE", "UCL"]
        }
      },
      {
        "UEFA CONFERENCE LEAGUE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/20296.png",
          "names": []
        }
      },
      {
        "UEFA EUROPA LEAGUE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2310.png",
          "names": ["EUROPA LEAGUE", "EUROPE UEFA CONFERENCE LEAGUE"]
        }
      },
      {
        "UEFA EUROPEAN CHAMPIONSHIP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/74.png",
          "names": ["EUROS", "UEFA EUROS"]
        }
      },
      {
        "UEFA SUPER CUP": {
          "logo": "https://i.gyazo.com/3b786181aba130321b85c0e2f9604652.png",
          "names": ["EUROPEAN SUPER CUP"]
        }
      },
      {
        "UEFA WOMEN'S CHAMPIONS LEAGUE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2408.png",
          "names": ["UCL WOMEN", "UEFA WOMEN", "WOMEN'S CHAMPIONS LEAGUE"]
        }
      },
      {
        "USL CHAMPIONSHIP": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2292.png",
          "names": ["UNITED SOCCER LEAGUE CHAMPIONSHIP", "USLC"]
        }
      },
      {
        "USL LEAGUE ONE": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2452.png",
          "names": ["UNITED SOCCER LEAGUE LEAGUE ONE", "USL 1", "USL1"]
        }
      },
      {
        "WORLD CUP QUALIFIERS": {
          "logo": "https://i.gyazo.com/1c4aa937f5ea01b0f29bb27adb59884c.png",
          "names": []
        }
      },
      {
        "WSL": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/leaguelogos/soccer/500/2314.png",
          "names": [
            "BARCLAY'S WOMEN'S SUPER LEAGUE",
            "ENGLISH WOMEN'S SUPER LEAGUE",
            "FA WSL",
            "WOMEN'S SUPER LEAGUE"
          ]
        }
      }
    ],
    "Tennis.Dummy.us": [
      {
        "TENNIS": {
          "logo": "https://i.gyazo.com/b5e83afc3a75dacfb831abe975fd3821.png",
          "names": []
        }
      }
    ],
    "UFC.247.Dummy.us": [
      {
        "UFC": {
          "logo": "https://1000logos.net/wp-content/uploads/2017/06/Logo-UFC-500x313.png",
          "names": ["UFC FIGHT NIGHT"]
        }
      }
    ],
    "WNBA.dummy.us": [
      {
        "WNBA": {
          "logo": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/wnba.png",
          "names": ["NBA W", "WOMEN'S NATIONAL BASKETBALL ASSOCIATION"]
        }
      }
    ]
  },
  "teams": {
    "NBA": [
      "76ers",
      "Atlanta Hawks",
      "Blazers",
      "Boston Celtics",
      "Brooklyn Nets",
      "Bucks",
      "Bulls",
      "Cavaliers",
      "Celtics",
      "Charlotte Hornets",
      "Chicago Bulls",
      "Cleveland Cavaliers",
      "Clippers",
      "Dallas Mavericks",
      "Denver Nuggets",
      "Detroit Pistons",
      "Golden State Warriors",
      "Grizzlies",
      "Hawks",
      "Heat",
      "Hornets",
      "Houston Rockets",
      "Indiana Pacers",
      "Jazz",
      "Kings",
      "Knicks",
      "Lakers",
      "Los Angeles Clippers",
      "Los Angeles Lakers",
      "Magic",
      "Mavericks",
      "Memphis Grizzlies",
      "Miami Heat",
      "Milwaukee Bucks",
      "Minnesota Timberwolves",
      "Nets",
      "New Orleans Pelicans",
      "New York Knicks",
      "Nuggets",
      "Oklahoma City Thunder",
      "Orlando Magic",
      "Pacers",
      "Pelicans",
      "Philadelphia 76ers",
      "Phoenix Suns",
      "Pistons",
      "Portland Trail Blazers",
      "Raptors",
      "Rockets",
      "Sacramento Kings",
      "San Antonio Spurs",
      "Sixers",
      "Spurs",
      "Suns",
      "Thunder",
      "Timberwolves",
      "Toronto Raptors",
      "Trail Blazers",
      "Utah Jazz",
      "Warriors",
      "Washington Wizards",
      "Wizards",
      "Wolves"
    ],
    "NFL": [
      "49ers",
      "9ers",
      "Arizona Cardinals",
      "Atlanta Falcons",
      "Baltimore Ravens",
      "Bears",
      "Bengals",
      "Bills",
      "Broncos",
      "Browns",
      "Buccaneers",
      "Buffalo Bills",
      "Cardinals",
      "Carolina Panthers",
      "Chargers",
      "Chicago Bears",
      "Chiefs",
      "Cincinnati Bengals",
      "Cleveland Browns",
      "Colts",
      "Commanders",
      "Cowboys",
      "Dallas Cowboys",
      "Denver Broncos",
      "Detroit Lions",
      "Dolphins",
      "Eagles",
      "Falcons",
      "Giants",
      "Green Bay Packers",
      "Houston Texans",
      "Indianapolis Colts",
      "Jacksonville Jaguars",
      "Jaguars",
      "Jets",
      "Kansas City Chiefs",
      "Las Vegas Raiders",
      "Lions",
      "Los Angeles Chargers",
      "Los Angeles Rams",
      "Miami Dolphins",
      "Minnesota Vikings",
      "New England Patriots",
      "New Orleans Saints",
      "New York Giants",
      "New York Jets",
      "Niners",
      "Packers",
      "Panthers",
      "Patriots",
      "Philadelphia Eagles",
      "Pittsburgh Steelers",
      "Raiders",
      "Rams",
      "Ravens",
      "Redskins",
      "Saints",
      "San Francisco 49ers",
      "Seahawks",
      "Seattle Seahawks",
      "Steelers",
      "Tampa Bay Buccaneers",
      "Tennessee Titans",
      "Texans",
      "Titans",
      "Vikings",
      "Washington Commanders",
      "Washington Redskins"
    ],
    "WNBA": [
      "Aces",
      "Atlanta Dream",
      "Chicago Sky",
      "Connecticut Sun",
      "Dallas Wings",
      "Dream",
      "Fever",
      "Golden State Valkyries",
      "Indiana Fever",
      "Las Vegas Aces",
      "Liberty",
      "Los Angeles Sparks",
      "Lynx",
      "Mercury",
      "Minnesota Lynx",
      "Mystics",
      "New York Liberty",
      "Phoenix Mercury",
      "Seattle Storm",
      "Sky",
      "Sparks",
      "Storm",
      "Sun",
      "Valkyries",
      "Washington Mystics",
      "Wings"
    ]
  }
}
import logging
from pathlib import Path

LOG_FMT = (
    "[%(asctime)s] "
    "%(levelname)-8s "
    "[%(name)s] "
    "%(message)-70s "
    "(%(filename)s:%(lineno)d)"
)

COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;41m",
    "reset": "\033[0m",
}


class ColorFormatter(logging.Formatter):
    def format(self, record) -> str:
        color = COLORS.get(record.levelname, COLORS["reset"])

        levelname = record.levelname

        record.levelname = f"{color}{levelname:<8}{COLORS['reset']}"

        formatted = super().format(record)

        record.levelname = levelname

        return formatted


def get_logger(name: str | None = None) -> logging.Logger:
    if not name:
        name = Path(__file__).stem

    logger = logging.getLogger(name)

    if not logger.hasHandlers():
        handler = logging.StreamHandler()

        formatter = ColorFormatter(LOG_FMT, datefmt="%Y-%m-%d | %H:%M:%S")

        handler.setFormatter(formatter)

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

        logger.propagate = False

    return logger


__all__ = ["get_logger", "ColorFormatter"]

import asyncio
import logging
import random
import re
from collections.abc import Awaitable, Callable
from functools import partial
from typing import TypeVar
from urllib.parse import urlencode, urljoin

import httpx
from playwright.async_api import Browser, BrowserContext, Playwright, Request

from .logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class Network:
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0"
    )

    proxy_base = "https://stream.nvrmind.xyz"

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=5,
            follow_redirects=True,
            headers={"User-Agent": Network.UA},
            http2=True,
        )

    @staticmethod
    def build_proxy_url(
        tag: str,
        path: str,
        query: dict | None = None,
    ) -> str:

        tag = tag.lower()

        return (
            f"{urljoin(network.proxy_base, f'{tag}/{path}')}?{urlencode(query)}"
            if query
            else urljoin(network.proxy_base, f"{tag}/{path}")
        )

    async def request(
        self,
        url: str,
        log: logging.Logger | None = None,
        **kwargs,
    ) -> httpx.Response | None:

        log = log or logger

        try:
            r = await self.client.get(url, **kwargs)

            r.raise_for_status()

            return r
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            log.error(f'Failed to fetch "{url}": {e}')

            return ""

    async def get_base(self, mirrors: list[str]) -> str | None:
        random.shuffle(mirrors)

        for mirror in mirrors:
            if not (r := await self.request(mirror)):
                continue

            elif r.status_code != 200:
                continue

            return mirror

    @staticmethod
    async def safe_process(
        fn: Callable[[], Awaitable[T]],
        url_num: int,
        timeout: int | float = 15,
        log: logging.Logger | None = None,
    ) -> T | None:

        log = log or logger

        task = asyncio.create_task(fn())

        try:
            return await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            log.warning(f"URL {url_num}) Timed out after {timeout}s, skipping event")

            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            except Exception as e:
                log.debug(f"URL {url_num}) Ignore exception after timeout: {e}")

            return
        except Exception as e:
            log.error(f"URL {url_num}) Unexpected error: {e}")

            return

    @staticmethod
    def capture_req(
        req: Request,
        captured: list[str],
        got_one: asyncio.Event,
    ) -> None:

        invalids = ["amazonaws", "knitcdn"]

        escaped = [re.escape(i) for i in invalids]

        pattern = re.compile(
            rf"^(?!.*({'|'.join(escaped)})).*\.m3u8",
            re.IGNORECASE,
        )

        if pattern.search(req.url):
            captured.append(req.url)
            got_one.set()

    async def process_event(
        self,
        url: str,
        url_num: int,
        context: BrowserContext,
        timeout: int | float = 10,
        log: logging.Logger | None = None,
    ) -> str | None:

        log = log or logger

        page = await context.new_page()

        captured: list[str] = []

        got_one = asyncio.Event()

        handler = partial(
            self.capture_req,
            captured=captured,
            got_one=got_one,
        )

        page.on("request", handler)

        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=15_000,
            )

            wait_task = asyncio.create_task(got_one.wait())

            try:
                await asyncio.wait_for(wait_task, timeout=timeout)
            except asyncio.TimeoutError:
                log.warning(f"URL {url_num}) Timed out waiting for M3U8.")

                return

            finally:
                if not wait_task.done():
                    wait_task.cancel()

                    try:
                        await wait_task
                    except asyncio.CancelledError:
                        pass

            if captured:
                log.info(f"URL {url_num}) Captured M3U8")

                return captured[0]

            log.warning(f"URL {url_num}) No M3U8 captured after waiting.")

            return

        except Exception as e:
            log.warning(f"URL {url_num}) Exception while processing: {e}")

            return

        finally:
            page.remove_listener("request", handler)

            await page.close()

    @staticmethod
    async def browser(
        playwright: Playwright, browser: str = "internal"
    ) -> tuple[Browser, BrowserContext]:
        if browser == "external":
            brwsr = await playwright.chromium.connect_over_cdp("http://localhost:9222")

            context = brwsr.contexts[0]

        else:
            brwsr = await playwright.firefox.launch(headless=True)

            context = await brwsr.new_context(
                user_agent=Network.UA,
                ignore_https_errors=False,
                viewport={"width": 1366, "height": 768},
                device_scale_factor=1,
                locale="en-US",
                timezone_id="America/New_York",
                color_scheme="dark",
                permissions=["geolocation"],
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Upgrade-Insecure-Requests": "1",
                },
            )

            await context.add_init_script(
                """
            Object.defineProperty(navigator, "webdriver", { get: () => undefined });

            Object.defineProperty(navigator, "languages", {
            get: () => ["en-US", "en"],
            });

            Object.defineProperty(navigator, "plugins", {
            get: () => [1, 2, 3, 4],
            });

            const elementDescriptor = Object.getOwnPropertyDescriptor(
            HTMLElement.prototype,
            "offsetHeight"
            );

            Object.defineProperty(HTMLDivElement.prototype, "offsetHeight", {
            ...elementDescriptor,
            get: function () {
                if (this.id === "modernizr") {
                return 24;
                }
                return elementDescriptor.get.apply(this);
            },
            });

            Object.defineProperty(window.screen, "width", { get: () => 1366 });
            Object.defineProperty(window.screen, "height", { get: () => 768 });

            const getParameter = WebGLRenderingContext.prototype.getParameter;

            WebGLRenderingContext.prototype.getParameter = function (param) {
            if (param === 37445) return "Intel Inc."; //  UNMASKED_VENDOR_WEBGL
            if (param === 37446) return "Intel Iris OpenGL    Engine"; // UNMASKED_RENDERER_WEBGL
            return getParameter.apply(this, [param]);
            };

            const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                if (node.tagName === "IFRAME" && node.hasAttribute("sandbox")) {
                    node.removeAttribute("sandbox");
                }
                });
            });
            });

            observer.observe(document.documentElement, { childList: true, subtree: true });

            """
            )

        return brwsr, context


network = Network()

__all__ = ["network"]

log = get_logger(__name__)

# =========================
# Configuration
# =========================

TAG = "ISTRMEST"
BASE_URL = "https://istreameast.app"

CACHE_FILE = Cache(f"{TAG.lower()}.json", exp=3_600)

urls: dict[str, dict[str, str | float]] = {}

# =========================
# M3U8 Playlist Generator
# =========================

def create_m3u8_playlist(data: dict[str, dict], output_file: str) -> None:
    lines = ["#EXTM3U"]

    for name, info in data.items():
        tvg_id = info.get("id", "")
        logo = info.get("logo", "")
        url = info.get("url", "")

        if not url:
            continue

        group = name.split("]")[0].strip("[") if "]" in name else "Live"

        lines.append(
            f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" '
            f'group-title="{group}",{name}'
        )
        lines.append(url)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# =========================
# Event Stream Extraction
# =========================

async def process_event(url: str, url_num: int) -> str | None:
    pattern = re.compile(
        r"source:\s*window\.atob\(\s*'([^']+)'\s*\)",
        re.IGNORECASE,
    )

    if not (event_data := await network.request(url, log=log)):
        log.info(f"URL {url_num}) Failed to load url.")
        return

    soup = HTMLParser(event_data.content)

    if not (iframe := soup.css_first("iframe#wp_player")):
        log.warning(f"URL {url_num}) No iframe element found.")
        return

    if not (iframe_src := iframe.attributes.get("src")):
        log.warning(f"URL {url_num}) No iframe source found.")
        return

    if not (iframe_src_data := await network.request(iframe_src, log=log)):
        log.info(f"URL {url_num}) Failed to load iframe source.")
        return

    if not (match := pattern.search(iframe_src_data.text)):
        log.warning(f"URL {url_num}) No Clappr source found.")
        return

    log.info(f"URL {url_num}) Captured M3U8")

    return base64.b64decode(match[1]).decode("utf-8")


# =========================
# Event Discovery
# =========================

async def get_events(cached_keys: list[str]) -> list[dict[str, str]]:
    events = []

    if not (html_data := await network.request(BASE_URL, log=log)):
        return events

    pattern = re.compile(
        r"^(?:LIVE|(?:[1-9]|[12]\d|30)\s+minutes?\b)",
        re.IGNORECASE,
    )

    soup = HTMLParser(html_data.content)

    for link in soup.css("li.f1-podium--item > a.f1-podium--link"):
        li_item = link.parent

        if not (rank_elem := li_item.css_first(".f1-podium--rank")):
            continue

        if not (time_elem := li_item.css_first(".SaatZamanBilgisi")):
            continue

        time_text = time_elem.text(strip=True)

        if not pattern.search(time_text):
            continue

        sport = rank_elem.text(strip=True)

        if not (driver_elem := li_item.css_first(".f1-podium--driver")):
            continue

        event_name = driver_elem.text(strip=True)

        if inner_span := driver_elem.css_first("span.d-md-inline"):
            event_name = inner_span.text(strip=True)

        key = f"[{sport}] {event_name} ({TAG})"

        if key in cached_keys:
            continue

        if not (href := link.attributes.get("href")):
            continue

        events.append(
            {
                "sport": sport,
                "event": event_name,
                "link": href,
            }
        )

    return events


# =========================
# Main Scraper
# =========================

async def scrape() -> None:
    cached_urls = CACHE_FILE.load()
    cached_count = len(cached_urls)

    urls.update(cached_urls)

    log.info(f"Loaded {cached_count} event(s) from cache")
    log.info(f'Scraping from "{BASE_URL}"')

    events = await get_events(list(cached_urls.keys()))

    log.info(f"Processing {len(events)} new URL(s)")

    if events:
        now = Time.clean(Time.now()).timestamp()

        for i, ev in enumerate(events, start=1):
            if url := await process_event(ev["link"], i):
                sport = ev["sport"]
                event = ev["event"]
                link = ev["link"]

                key = f"[{sport}] {event} ({TAG})"

                tvg_id, logo = leagues.get_tvg_info(sport, event)

                entry = {
                    "url": url,
                    "logo": logo,
                    "base": "https://gooz.aapmains.net",
                    "timestamp": now,
                    "id": tvg_id or "Live.Event.us",
                    "link": link,
                }

                urls[key] = cached_urls[key] = entry

    if new_count := len(cached_urls) - cached_count:
        log.info(f"Collected and cached {new_count} new event(s)")
    else:
        log.info("No new events found")

    CACHE_FILE.write(cached_urls)

    # Generate M3U8 playlist
    create_m3u8_playlist(cached_urls, f"{TAG.lower()}.m3u8")
    log.info("M3U8 playlist generated")
