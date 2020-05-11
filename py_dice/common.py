import re
from functools import reduce
from uuid import UUID

from logbook import Logger
from py_dice import core, dcs, dice10k
from slack import WebClient

log = Logger(__name__)


def format_dice_emojis(roll_val: list) -> str:
    return reduce(format_dice_emoji, roll_val, "")


def format_dice_emoji(x1: str, x2: int) -> str:
    return f"{x1} :die{x2}:"


def fetch_die_val(acc: list, x: dict) -> list:
    die = x["text"]["text"]
    acc.append(int(re.search(r"\d+", die).group()))
    return acc


def is_valid_uuid(uuid_to_test: str, version: int = 4) -> bool:
    try:
        UUID(uuid_to_test, version=version)
    except ValueError:
        return False
    return True


def who_can_steal(game_id: str, winning_threshold: int = 3000) -> list:
    dice10k_state = dice10k.fetch_game(game_id)
    players = dice10k_state["players"]
    if len(players) > 1:
        previous_player = next(p for p in players if p["turn-order"] == 1)
    else:
        previous_player = players[0]
    matched_players = []
    for player in players:
        log.info(
            f"{players} \n"
            f"{player} \n"
            f"{bool((dice10k_state['pending-points'] + player['points']) < winning_threshold)} \n"
            f"{player['ice-broken?']}\n"
            f"{is_robbable(game_id=game_id, username=previous_player['name'])}\n"
            f"{bool(previous_player['points'] >= 1000)}"
        )
        if (
            # Total points won't put you over the winning threshold
            bool(
                (dice10k_state["pending-points"] + player["points"]) < winning_threshold
            )
            # Current user broke the ice
            and player["ice-broken?"]
            # Previous player is robbable
            and is_robbable(game_id=game_id, username=previous_player["name"])
            # Verify current player has 1000 points
            and bool(previous_player["points"] >= 1000)
        ):
            matched_players.append(player["name"])
    log.info(f"stealable players: {matched_players}")
    return matched_players


def game_over(
    game_info: dict, slack_client: WebClient, winner: str, response_url: str = ""
):
    core.delete_message(response_url=response_url)
    core.build_game_panel(
        slack_client=slack_client, game_info=game_info, state="completed"
    )
    slack_client.chat_postMessage(
        **dcs.message.create(
            game_id=game_info["game_id"],
            channel_id=game_info["channel"],
            message=f"Game has completed @{winner} has won",
        )
        .in_thread(thread_id=game_info["parent_message_ts"])
        .build()
    )


def is_game_over(
    game_info: dict,
    slack_client: WebClient,
    response_url: str = "",
    winning_threshold: int = 3000,
) -> bool:
    dice10k_state = dice10k.fetch_game(game_info["game_id"])
    winner = ""
    if dice10k_state.get("players", None):
        for p in dice10k_state["players"]:
            if p["points"] == winning_threshold:
                winner = p["name"]
            elif (p["points"] + p["pending-points"] == winning_threshold) and not (
                who_can_steal(game_info["game_id"])
            ):
                winner = p["name"]
            elif p["points"] + p["pending-points"] > winning_threshold:
                log.exception(
                    f"{p['name']} has somehow surpassed the winning threshold"
                )
    if winner:
        game_over(
            game_info=game_info,
            slack_client=slack_client,
            winner=winner,
            response_url=response_url,
        )
        return True
    return False


def get_game_id(payload: dict) -> str:
    if is_valid_uuid(payload["actions"][0].get("block_id", "")):
        return payload["actions"][0]["block_id"]
    else:
        return payload["actions"][0]["value"]


def is_robbable(game_id: str, username: str) -> bool:
    # TODO: update to be checked once and maintained in state
    players = dice10k.fetch_game(game_id)["players"]
    player_info = next(p for p in players if p["name"] == username)
    if player_info["points"] >= 1000:
        return True
    else:
        return False


def is_broken(game_info: dict, username: str) -> bool:
    if (
        username in game_info["users"]
        and "ice_broken" not in game_info["users"][username]
    ):
        players = dice10k.fetch_game(game_info["game_id"])["players"]
        player_info = next(p for p in players if p["name"] == username)
        if player_info["points"] >= 1000:
            return True
    return False


def is_previous_winnable(game_id: str) -> bool:
    players = dice10k.fetch_game(game_id)["players"]
    previous_player = next(p for p in players if p["turn-order"] == 0)
    log.info(f"is_winnable {previous_player}")
    if previous_player["points"] + previous_player["pending-points"] == 3000:
        return True
    return False
