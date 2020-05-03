# coding=utf-8

from logbook import Logger
from py_dice import common, core, dcs, dice10k
from slack import WebClient

log = Logger(__name__)


def join_game(
    slack_client: WebClient, game_info: dict, slack_user_id: str, username: str
) -> dict:
    log.info("Action: Join Game")
    if username not in game_info["users"]:
        game_info["users"][username] = {
            "user_id": dice10k.add_player(game_info["game_id"], username)["player-id"],
            "slack_id": slack_user_id,
        }
        slack_client.chat_postMessage(
            **dcs.message.create(
                game_id=game_info["game_id"],
                channel_id=game_info["channel"],
                message=f"{username} has successfully joined the game",
            )
            .in_thread(thread_id=game_info["parent_message_ts"])
            .build()
        )
    return game_info


def pass_dice(
    slack_client: WebClient, game_info: dict, response_url: str, username: str
) -> None:
    log.info("Action: Pass Dice")
    core.build_game_panel(slack_client=slack_client, game_info=game_info)
    core.delete_message(response_url=response_url)
    response = dice10k.pass_turn(
        game_id=game_info["game_id"], user_id=game_info["users"][username]["user_id"]
    )
    turn_player = response["game-state"]["turn-player"]
    if turn_player in common.who_can_steal(game_info=game_info):
        message = (
            dcs.message.create(
                game_id=game_info["game_id"],
                channel_id=game_info["channel"],
                message=f"@{turn_player}",
            )
            .at_user(slack_id=game_info["users"][turn_player]["slack_id"])
            .in_thread(thread_id=game_info["parent_message_ts"])
        )
        if not common.is_previous_winnable(game_info=game_info):
            message.add_button(
                game_id=game_info["game_id"], text="Roll", action_id="roll_dice"
            )
        if game_info["users"][username].get("ice_broken", False) and (
            username in common.who_can_steal(game_info=game_info)
        ):
            message.add_button(
                game_id=game_info["game_id"], text="Steal", action_id="steal_dice"
            )
        slack_client.chat_postEphemeral(**message.build())
    else:
        core.roll_with_player_message(
            slack_client=slack_client,
            game_info=game_info,
            username=turn_player,
            steal=False,
        )
    return None


def pick_dice(
    slack_client: WebClient,
    game_info: dict,
    response_url: str,
    username: str,
    picks: list,
):
    log.info("Action: Picked Dice")
    response = dice10k.send_keepers(
        game_id=game_info["game_id"],
        user_id=game_info["users"][username]["user_id"],
        picks=picks,
    )
    if response["message"].startswith("PICK FAIL"):
        slack_client.chat_postEphemeral(
            **dcs.message.create(
                game_id=game_info["game_id"],
                channel_id=game_info["channel"],
                message=f"Pick failed, try again \n {common.format_dice_emojis(response['roll'])}",
            )
            .at_user(slack_id=game_info["users"][username]["slack_id"])
            .in_thread(thread_id=game_info["parent_message_ts"])
            .pick_die(roll_val=response["roll"])
            .build()
        )
    elif response["message"].startswith("It's not your turn"):
        players = game_info["dice10k_state"]["players"]
        current_player = next(p for p in players if p["turn-order"] == 0)
        core.roll_with_player_message(
            slack_client=slack_client,
            game_info=game_info,
            username=current_player["name"],
            steal=False,
        )
    else:
        ice_broken = next(
            p for p in response["game-state"]["players"] if p["name"] == username
        )["ice-broken?"]
        core.delete_message(response_url=response_url)
        slack_client.chat_postMessage(
            **dcs.message.create(
                game_id=game_info["game_id"],
                channel_id=game_info["channel"],
                message=f"{username}\n"
                f"Picked: {common.format_dice_emojis(picks)}\n"
                f"Remaining Dice: {response['game-state']['pending-dice']}\n",
            )
            .in_thread(thread_id=game_info["parent_message_ts"])
            .build()
        )
        if not (ice_broken or response.get("pending-points", 0) >= 1000):
            roll_dice(
                slack_client=slack_client,
                game_info=game_info,
                response_url=response_url,
                username=username,
            )
        else:
            slack_client.chat_postEphemeral(
                **dcs.message.create(
                    game_id=game_info["game_id"],
                    channel_id=game_info["channel"],
                    message=f"@{username}",
                )
                .add_button(
                    game_id=game_info["game_id"], text="Roll", action_id="roll_dice"
                )
                .add_button(
                    game_id=game_info["game_id"], text="Pass", action_id="pass_dice"
                )
                .at_user(slack_id=game_info["users"][username]["slack_id"])
                .in_thread(thread_id=game_info["parent_message_ts"])
                .build()
            )
    return game_info


def roll_dice(
    slack_client: WebClient, game_info: dict, response_url: str, username: str
) -> None:
    log.info("Action: Rolled Dice")
    core.build_game_panel(slack_client=slack_client, game_info=game_info)
    core.delete_message(response_url=response_url)
    core.roll_with_player_message(
        slack_client=slack_client, game_info=game_info, username=username, steal=False
    )
    return None


def steal_dice(
    slack_client: WebClient, game_info: dict, response_url: str, username: str
) -> None:
    log.info("Action: Steal Dice")
    core.delete_message(response_url=response_url)
    core.build_game_panel(slack_client=slack_client, game_info=game_info)
    core.roll_with_player_message(
        slack_client=slack_client, game_info=game_info, username=username, steal=True
    )
    return None


def start_game(
    slack_client: WebClient, game_info: dict, auto_break: bool = False
) -> dict:
    log.info("Action: Start Game")
    if auto_break:
        game_info["auto_break"] = True
    else:
        game_info["auto_break"] = False
    start_response = dice10k.start_game(game_id=game_info["game_id"])
    turn_player = start_response["turn-player"]
    core.build_game_panel(slack_client=slack_client, game_info=game_info)
    core.roll_with_player_message(
        slack_client=slack_client, game_info=game_info, username=turn_player
    )
    return game_info
