question_football = [
    {
    "id": 1,
    "question": "Which player attempted the most shots and how many shots did they take?",
    "query": "SELECT player, COUNT(*) AS total_shots FROM {table_name} WHERE event_type = 'shot' GROUP BY player HAVING COUNT(*) = (SELECT MAX(shot_count) FROM (SELECT COUNT(*) AS shot_count FROM {table_name} WHERE event_type = 'shot' GROUP BY player) s);",
    "exp": "Group all shot events by player, count them, and return the player with the highest shot count.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who took the most shots in the match?",
        "Which player attempted the highest number of shots?",
        "Show the player that recorded the most shot attempts."
    ],
    "primary_key": "player"
    },
    {
    "id": 2,
    "question": "Which player scored the most goals and how many goals did they score?",
    "query": "SELECT player, COUNT(*) AS total_goals FROM {table_name} WHERE event_type = 'goal' GROUP BY player HAVING COUNT(*) = (SELECT MAX(goal_count) FROM (SELECT COUNT(*) AS goal_count FROM {table_name} WHERE event_type = 'goal' GROUP BY player) g);",
    "exp": "Count goal events per player and return the player with the maximum goals.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who scored the most goals?",
        "Which player had the highest goal tally?",
        "Show the top scorer and their goal count."
    ],
    "primary_key": "player"
    },
    {
    "id": 3,
    "question": "Which player committed the most fouls and how many fouls did they commit?",
    "query": "SELECT player, COUNT(*) AS total_fouls FROM {table_name} WHERE event_type = 'foul' GROUP BY player HAVING COUNT(*) = (SELECT MAX(foul_count) FROM (SELECT COUNT(*) AS foul_count FROM {table_name} WHERE event_type = 'foul' GROUP BY player) f);",
    "exp": "Group foul events by player, count them, and return the one with the highest total.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who committed the most fouls?",
        "Which player broke the rules most often?",
        "Show me the player with the highest foul count."
    ],
    "primary_key": "player"
    },
    {
    "id": 4,
    "question": "Which player received the most yellow cards?",
    "query": "SELECT player, COUNT(*) AS yellow_cards FROM {table_name} WHERE event_type = 'yellow card' GROUP BY player HAVING COUNT(*) = (SELECT MAX(yellow_count) FROM (SELECT COUNT(*) AS yellow_count FROM {table_name} WHERE event_type = 'yellow card' GROUP BY player) y);",
    "exp": "Count yellow card events for each player and return the highest.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who received the most yellow cards?",
        "Which player got the highest number of cautions?",
        "Show the player with the most yellows."
    ],
    "primary_key": "player"
    },
    {
    "id": 5,
    "question": "Which players were sent off and at what minute?",
    "query": "SELECT player, minute FROM {table_name} WHERE event_type IN ('red card', 'sent off') ORDER BY minute ASC;",
    "exp": "Return all players who were sent off, showing the minute of the incident.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who received red cards and when?",
        "List players who were sent off along with the time.",
        "Which players got sent off and at what minute?"
    ],
    "primary_key": "player"
    },
    {
    "id": 6,
    "question": "Which team won the most free kicks and how many free kicks did they win?",
    "query": "SELECT team, COUNT(*) AS total_free_kicks FROM {table_name} WHERE event_type = 'free kick' GROUP BY team HAVING COUNT(*) = (SELECT MAX(fk_count) FROM (SELECT COUNT(*) AS fk_count FROM {table_name} WHERE event_type = 'free kick' GROUP BY team) fk);",
    "exp": "Count free kick events per team and return the one with the highest total.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team was awarded the most free kicks?",
        "Show the team that earned the highest number of free kicks.",
        "Who had the most free kick opportunities?"
    ],
    "primary_key": "team"
    },
    {
    "id": 7,
    "question": "Which player was caught offside the most times?",
    "query": "SELECT player, COUNT(*) AS offsides FROM {table_name} WHERE event_type = 'offside' GROUP BY player HAVING COUNT(*) = (SELECT MAX(os_count) FROM (SELECT COUNT(*) AS os_count FROM {table_name} WHERE event_type = 'offside' GROUP BY player) o);",
    "exp": "Group offside events by player and return the player with the highest count.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who was offside the most?",
        "Which attacker committed the most offsides?",
        "Show the player with the highest offside count."
    ],
    "primary_key": "player"
    },
    {
    "id": 8,
    "question": "Which team took the most corner kicks and how many corners did they take?",
    "query": "SELECT team, COUNT(*) AS total_corners FROM {table_name} WHERE event_type = 'corner kick' GROUP BY team HAVING COUNT(*) = (SELECT MAX(corner_count) FROM (SELECT COUNT(*) AS corner_count FROM {table_name} WHERE event_type = 'corner kick' GROUP BY team) c);",
    "exp": "Count corner kick events per team and return the maximum.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team earned the most corners?",
        "Show the team with the highest number of corner kicks.",
        "Who took the most corner kicks?"
    ],
    "primary_key": "team"
    },
    {
    "id": 9,
    "question": "How many goals did each player score directly after a free kick or corner kick?",
    "query": "SELECT player, COUNT(*) AS set_piece_goals FROM {table_name} WHERE event_type = 'goal' AND description LIKE '%free kick%' OR description LIKE '%corner kick%' GROUP BY player;",
    "exp": "Check goal events whose description indicates they came from a free kick or corner kick, then group by scorer.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players scored goals from set pieces?",
        "How many set-piece goals did each player score?",
        "Show goals scored by players from free kicks or corners."
    ],
    "primary_key": "player"
    },
    {
    "id": 10,
    "question": "Which defenders committed fouls that resulted in a yellow or red card?",
    "query": "SELECT player, COUNT(*) AS card_fouls FROM {table_name} WHERE event_type = 'foul' AND description LIKE '%card%' GROUP BY player HAVING COUNT(*) > 0 ORDER BY card_fouls DESC;",
    "exp": "Identify fouls where the description indicates a card was given, group by the fouling player.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players committed fouls that resulted in bookings?",
        "Show players whose fouls led to yellow or red cards.",
        "Which defenders caused the referee to give a card?"
    ],
    "primary_key": "player"
    },
    {
    "id": 11,
    "question": "Which team had the best goal conversion rate (goals per shot) among teams with at least 5 shot attempts?",
    "query": "WITH per_team AS ( \
                SELECT \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots, \
                    SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS total_goals \
                FROM {table_name} \
                GROUP BY team \
                HAVING SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) >= 5 \
                ), \
                conv AS ( \
                SELECT \
                    team, \
                    total_shots, \
                    total_goals, \
                    (total_goals * 1.0) / NULLIF(total_shots, 0) AS conv_exact, \
                    ROUND((total_goals * 100.0) / NULLIF(total_shots, 0), 2) AS conversion_percentage \
                FROM per_team \
                ), \
                best AS (SELECT MAX(conv_exact) AS best_conv FROM conv) \
                SELECT team, total_shots, total_goals, conversion_percentage \
                FROM conv \
                WHERE conv_exact = (SELECT best_conv FROM best);",
    "exp": "Compute shot and goal counts per team, filter teams with at least 5 shots, calculate conversion %, and return the team with the highest value.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team converted the most shots into goals?",
        "Find the team with the best scoring efficiency.",
        "Which team has the highest goals-per-shot ratio with minimum 5 shots?"
    ],
    "primary_key": "team"
    },
    {
    "id": 12,
    "question": "Which player had the best shot conversion rate (goals per shot) among players with at least 3 shots?",
    "query": "WITH per_player AS ( \
                SELECT \
                    player, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots, \
                    SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS total_goals \
                FROM {table_name} \
                GROUP BY player \
                HAVING SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) >= 3 \
                ), \
                conv AS ( \
                SELECT \
                    player, \
                    total_shots, \
                    total_goals, \
                    (total_goals * 1.0) / NULLIF(total_shots, 0) AS conv_exact, \
                    ROUND((total_goals * 100.0) / NULLIF(total_shots, 0), 2) AS conversion_percentage \
                FROM per_player \
                ), \
                best AS (SELECT MAX(conv_exact) AS best_conv FROM conv) \
                SELECT player, total_shots, total_goals, conversion_percentage \
                FROM conv \
                WHERE conv_exact = (SELECT best_conv FROM best);",
    "exp": "Identify players with at least 3 shots, compute their goal conversion %, and output the highest.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player was the most efficient goal scorer?",
        "Who converted the highest ratio of shots into goals?",
        "Find the player with the best finishing rate."
    ],
    "primary_key": "player"
    },
    {
    "id": 13,
    "question": "Show cumulative goals over time for each team across the match.",
    "query": "WITH goal_events AS ( \
                SELECT minute, team, COUNT(*) AS goals_in_minute \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                GROUP BY minute, team \
                ) \
                SELECT \
                minute, \
                team, \
                goals_in_minute, \
                SUM(goals_in_minute) OVER (PARTITION BY team ORDER BY minute) AS cumulative_goals \
                FROM goal_events \
                ORDER BY team ASC, minute ASC;",
    "exp": "Group goal events per minute and accumulate totals using a window function to show goal progression.",
    "variables": ["table_name"],
    "paraphrases": [
        "How did each team's total goals build up over time?",
        "Show running tally of goals per team.",
        "Provide the minute-by-minute cumulative goal count."
    ],
    "primary_key": ["team", "minute"]
    },
    {
    "id": 14,
    "question": "Find 5-minute periods where a team recorded at least 3 shots, indicating high-pressure phases.",
    "query": "WITH shot_windows AS ( \
                SELECT \
                    team, \
                    ((minute - 1) / 5) AS window_index, \
                    COUNT(*) AS shots_in_window \
                FROM {table_name} \
                WHERE event_type = 'shot' \
                GROUP BY team, ((minute - 1) / 5) \
                ) \
                SELECT \
                team, \
                (window_index * 5 + 1) AS window_start_minute, \
                (window_index * 5 + 5) AS window_end_minute, \
                shots_in_window \
                FROM shot_windows \
                WHERE shots_in_window >= 3 \
                ORDER BY shots_in_window DESC, team ASC;",
    "exp": "Divide the match into 5-minute windows, count each team's shots, and return windows with 3+ shots.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which 5-minute intervals saw teams take at least 3 shots?",
        "Identify bursts of attacking pressure.",
        "Show time windows where teams generated high shot volume."
    ],
    "primary_key": ["team", "window_start_minute", "window_end_minute"]
    },
    {
    "id": 15,
    "question": "How many goals did each team score within 2 minutes after a corner kick or free kick?",
    "query": "WITH set_pieces AS ( \
                SELECT minute AS sp_minute, team \
                FROM {table_name} \
                WHERE event_type IN ('corner kick', 'free kick') \
                ), \
                goals AS ( \
                SELECT minute AS goal_minute, team \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                ) \
                SELECT \
                sp.team, \
                COUNT(*) AS goals_after_set_piece \
                FROM set_pieces sp \
                JOIN goals g \
                ON g.team = sp.team \
                AND g.goal_minute > sp.sp_minute \
                AND g.goal_minute <= sp.sp_minute + 2 \
                GROUP BY sp.team \
                ORDER BY goals_after_set_piece DESC;",
    "exp": "Find goals scored shortly after set pieces by joining set-piece minutes to goal minutes within 2 minutes.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which teams turned set pieces into quick goals?",
        "Show goals scored soon after a free kick or corner.",
        "How many goals came immediately after a set piece?"
    ],
    "primary_key": "team"
    },
    {
    "id": 16,
    "question": "Which players received a yellow card and later a red card, and how long was the gap between the two events?",
    "query": "WITH yellows AS ( \
                SELECT player, MIN(minute) AS yellow_minute \
                FROM {table_name} \
                WHERE event_type = 'yellow card' \
                GROUP BY player \
                ), \
                reds AS ( \
                SELECT player, MIN(minute) AS red_minute \
                FROM {table_name} \
                WHERE event_type IN ('red card', 'sent off') \
                GROUP BY player \
                ) \
                SELECT \
                y.player, \
                y.yellow_minute, \
                r.red_minute, \
                (r.red_minute - y.yellow_minute) AS minutes_between_cards \
                FROM yellows y \
                JOIN reds r ON y.player = r.player \
                WHERE r.red_minute > y.yellow_minute \
                ORDER BY minutes_between_cards ASC;",
    "exp": "Locate earliest yellow and red card for each player and calculate time interval between the two.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who received a yellow before being sent off, and after how long?",
        "Which players progressed from yellow to red?",
        "Show the timings between yellow and red card incidents."
    ],
    "primary_key": "player"
    },
    {
    "id": 17,
    "question": "Which team committed the most fouls in the final 15 minutes of the match?",
    "query": "SELECT team, COUNT(*) AS fouls_last_15 \
                FROM {table_name} \
                WHERE event_type = 'foul' AND minute >= 76 \
                GROUP BY team \
                HAVING COUNT(*) = ( \
                SELECT MAX(foul_count) \
                FROM (SELECT team, COUNT(*) AS foul_count FROM {table_name} WHERE event_type = 'foul' AND minute >= 76 GROUP BY team) f \
                );",
    "exp": "Restrict fouls to minutes 76–90, count per team, and return the maximum.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team fouled most in the closing minutes?",
        "Show late-game foul leaders.",
        "Who committed the most fouls in the last 15 minutes?"
    ],
    "primary_key": "team"
    },
    {
    "id": 18,
    "question": "For each team, how many fouls, yellow cards, and red cards did they receive?",
    "query": "SELECT \
                team, \
                SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls, \
                SUM(CASE WHEN event_type = 'yellow card' THEN 1 ELSE 0 END) AS yellow_cards, \
                SUM(CASE WHEN event_type IN ('red card','sent off') THEN 1 ELSE 0 END) AS red_cards \
                FROM {table_name} \
                GROUP BY team \
                ORDER BY fouls DESC, yellow_cards DESC, red_cards DESC;",
    "exp": "Summarize disciplinary events per team: fouls, yellow cards, red cards.",
    "variables": ["table_name"],
    "paraphrases": [
        "Give foul and card totals per team.",
        "Which team had the worst discipline?",
        "Show fouls, yellows, and reds for each team."
    ],
    "primary_key": "team"
    },
    {
    "id": 19,
    "question": "Which players took the most shots after the 80th minute?",
    "query": "SELECT player, COUNT(*) AS late_shots \
                FROM {table_name} \
                WHERE event_type = 'shot' AND minute >= 80 \
                GROUP BY player \
                ORDER BY late_shots DESC, player ASC;",
    "exp": "Filter shot events to late-game moments (80th minute onward) then group by player.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who attempted shots late in the match?",
        "Which players were most active in shooting after minute 80?",
        "Show late-game shot attempts per player."
    ],
    "primary_key": "player"
    },
    {
    "id": 20,
    "question": "Which minute had the highest total number of key events?",
    "query": "WITH per_minute AS ( \
                SELECT minute, COUNT(*) AS total_events \
                FROM {table_name} \
                WHERE event_type IN ('shot','goal','foul','yellow card','red card','sent off','offside','corner kick','free kick') \
                GROUP BY minute \
                ), \
                mx AS (SELECT MAX(total_events) AS max_events FROM per_minute) \
                SELECT minute, total_events \
                FROM per_minute \
                WHERE total_events = (SELECT max_events FROM mx);",
    "exp": "Count key events per minute across the match, then return the minute with the highest event count.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which minute was the most intense?",
        "Show the minute with the most combined events.",
        "What was the busiest minute of the match?"
    ],
    "primary_key": "minute"
    },
    {
    "id": 21,
    "question": "Which player scored the most goals between minutes {x1} and {x2}, and how many goals did they score?",
    "query": "SELECT\
                player,\
                COUNT(*) AS goals_scored\
                FROM {table_name}\
                WHERE event_type = 'goal'\
                AND minute BETWEEN {x1} AND {x2}\
                GROUP BY player\
                HAVING COUNT(*) = (\
                SELECT MAX(goals_in_range)\
                FROM (\
                    SELECT COUNT(*) AS goals_in_range\
                    FROM {table_name}\
                    WHERE event_type = 'goal'\
                    AND minute BETWEEN {x1} AND {x2}\
                    GROUP BY player\
                ) g\
                );",
    "exp": "Filter goal events to the minute range [{x1}, {x2}], group by player, count goals, and return the player or players with the highest goal count in that period.",
    "variables": ["table_name", "x1", "x2"],
    "paraphrases": [
        "Between minutes {x1} and {x2}, which player scored the most goals?",
        "Who was the top scorer in the time window from minute {x1} to {x2}?",
        "Show the player with the highest number of goals between minutes {x1} and {x2} and how many they scored."
    ],
    "primary_key": "player"
    },
    {
    "id": 22,
    "question": "Which team attempted the most shots between minutes {x1} and {x2}, and how many shots did they take?",
    "query": "SELECT\
                team,\
                COUNT(*) AS shots_attempted\
                FROM {table_name}\
                WHERE event_type = 'shot'\
                AND minute BETWEEN {x1} AND {x2}\
                GROUP BY team\
                HAVING COUNT(*) = (\
                SELECT MAX(shots_in_range)\
                FROM (\
                    SELECT COUNT(*) AS shots_in_range\
                    FROM {table_name}\
                    WHERE event_type = 'shot'\
                    AND minute BETWEEN {x1} AND {x2}\
                    GROUP BY team\
                ) s\
                );",
    "exp": "Restrict events to shots in the minute range [{x1}, {x2}], aggregate their counts per team, and select the team(s) with the maximum shot volume.",
    "variables": ["table_name", "x1", "x2"],
    "paraphrases": [
        "From minute {x1} to {x2}, which team took the most shots?",
        "Which team was most trigger-happy between minutes {x1} and {x2}?",
        "Show the team with the highest shot count in the period {x1}–{x2}."
    ],
    "primary_key": "team"
    },
    {
    "id": 23,
    "question": "Which player took the most shots without scoring a goal?",
    "query": "WITH player_shots AS (\
                SELECT\
                    player,\
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots,\
                    SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS total_goals\
                FROM {table_name}\
                GROUP BY player\
                )\
                SELECT\
                player,\
                total_shots\
                FROM player_shots\
                WHERE total_goals = 0\
                AND total_shots = (\
                    SELECT MAX(no_goal_shots)\
                    FROM (\
                    SELECT total_shots AS no_goal_shots\
                    FROM player_shots\
                    WHERE total_goals = 0\
                    ) t\
                );",
    "exp": "Aggregate shot and goal counts per player, keep only players who scored no goals, and return the one(s) who nevertheless took the most shots.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who was the unluckiest or most wasteful finisher (most shots, zero goals)?",
        "Which player fired the most shots without finding the net?",
        "Show the player with the highest shot count but no goals."
    ],
    "primary_key": "player"
    },
    {
    "id": 24,
    "question": "Which player scored their first goal in the fewest minutes after their first shot, and how many minutes did it take?",
    "query": "WITH first_shot AS (\
                SELECT\
                    player,\
                    MIN(minute) AS first_shot_minute\
                FROM {table_name}\
                WHERE event_type IN ('shot','goal')\
                GROUP BY player\
                ),\
                first_goal AS (\
                SELECT\
                    player,\
                    MIN(minute) AS first_goal_minute\
                FROM {table_name}\
                WHERE event_type = 'goal'\
                GROUP BY player\
                ),\
                deltas AS (\
                SELECT\
                    s.player,\
                    s.first_shot_minute,\
                    g.first_goal_minute,\
                    (g.first_goal_minute - s.first_shot_minute) AS minutes_to_first_goal\
                FROM first_shot s\
                JOIN first_goal g\
                    ON s.player = g.player\
                WHERE g.first_goal_minute >= s.first_shot_minute\
                ),\
                best AS (\
                SELECT MIN(minutes_to_first_goal) AS min_delta\
                FROM deltas\
                )\
                SELECT\
                player,\
                first_shot_minute,\
                first_goal_minute,\
                minutes_to_first_goal\
                FROM deltas\
                WHERE minutes_to_first_goal = (SELECT min_delta FROM best);",
    "exp": "For each player, find the minute of their first shot and first goal, compute the difference, and return the player(s) who reached their first goal in the shortest time after their first shot.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who got off the mark (first goal) the quickest after their first attempt?",
        "Which player needed the least time between their first shot and first goal?",
        "Show the fastest scorer in terms of minutes from first shot to first goal."
    ],
    "primary_key": "player"
    },
    {
    "id": 25,
    "question": "List all sequences where the same team recorded shots in three consecutive minutes.",
    "query": "WITH team_shots AS (\
                SELECT DISTINCT minute, team\
                FROM {table_name}\
                WHERE event_type = 'shot'\
                )\
                SELECT\
                t1.team,\
                t1.minute AS minute_1,\
                t2.minute AS minute_2,\
                t3.minute AS minute_3\
                FROM team_shots t1\
                JOIN team_shots t2\
                ON t2.team = t1.team\
                AND t2.minute = t1.minute + 1\
                JOIN team_shots t3\
                ON t3.team = t1.team\
                AND t3.minute = t2.minute + 1\
                ORDER BY t1.team, minute_1;",
    "exp": "Collapse shot events to unique (team, minute) pairs, then self-join to detect runs of three consecutive minutes where the same team registered at least one shot.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which teams had shot attempts in three straight minutes, and what were those minutes?",
        "Show all three-minute stretches of uninterrupted shooting by a single team.",
        "Find sequences where a team recorded shots in three consecutive minutes."
    ],
    "primary_key": ["team", "minute_1", "minute_2", "minute_3"]
    },
    {
    "id": 26,
    "question": "For each team, how many total shots did they take, how many were goals, and how many were non-scoring shots?",
    "query": "SELECT\
                team,\
                SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots,\
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS goals,\
                (SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) -\
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END)) AS non_scoring_shots\
                FROM {table_name}\
                GROUP BY team\
                ORDER BY total_shots DESC, goals DESC, team ASC;",
    "exp": "Treat both 'shot' and 'goal' events as shot attempts, count them per team, separate those that resulted in goals, and derive non-scoring shots by subtraction.",
    "variables": ["table_name"],
    "paraphrases": [
        "Give a shot breakdown for each team: total shots, goals, and non-goal shots.",
        "How many shots and goals did each team have, and how many shots did not result in goals?",
        "Show shooting summary per team, splitting goals and missed shots."
    ],
    "primary_key": "team"
    },
    {
    "id": 27,
    "question": "Which players had the highest offside-to-shot ratio among those with at least 3 offsides?",
    "query": "WITH per_player AS (\
                SELECT\
                    player,\
                    SUM(CASE WHEN event_type = 'offside' THEN 1 ELSE 0 END) AS offsides,\
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS shots\
                FROM {table_name}\
                GROUP BY player\
                HAVING SUM(CASE WHEN event_type = 'offside' THEN 1 ELSE 0 END) >= 3\
                ),\
                ratios AS (\
                SELECT\
                    player,\
                    offsides,\
                    shots,\
                    (offsides * 1.0) / NULLIF(shots, 0) AS ratio_exact,\
                    ROUND((offsides * 1.0) / NULLIF(shots, 0), 2) AS offside_to_shot_ratio\
                FROM per_player\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                player,\
                offsides,\
                shots,\
                offside_to_shot_ratio\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "For players with at least 3 offsides, compute the ratio of offsides to shots and return those with the highest ratio.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players were caught offside the most relative to how often they shot?",
        "Show players with the worst offside-to-shot ratio, among those frequently offside.",
        "Identify players who went offside a lot compared to their shot volume."
    ],
    "primary_key": "player"
    },
    {
    "id": 28,
    "question": "Show a 10-minute rolling total of fouls committed by each team to capture momentum and aggression shifts.",
    "query": "WITH fouls_per_minute AS (\
                SELECT\
                    minute,\
                    team,\
                    COUNT(*) AS fouls_in_minute\
                FROM {table_name}\
                WHERE event_type = 'foul'\
                GROUP BY minute, team\
                )\
                SELECT\
                minute,\
                team,\
                fouls_in_minute,\
                SUM(fouls_in_minute) OVER (\
                    PARTITION BY team\
                    ORDER BY minute\
                    ROWS BETWEEN 9 PRECEDING AND CURRENT ROW\
                ) AS fouls_last_10_minutes\
                FROM fouls_per_minute\
                ORDER BY team ASC, minute ASC;",
    "exp": "First aggregate fouls by minute and team, then apply a window function over the previous 10 minutes (current plus 9 preceding rows) to compute a rolling foul count per team.",
    "variables": ["table_name"],
    "paraphrases": [
        "How did each team’s foul intensity evolve, looking at a rolling 10-minute window?",
        "Show 10-minute moving sums of fouls per team across the match.",
        "Provide a rolling foul count per team over 10-minute spans."
    ],
    "primary_key": ["team", "minute"]
    },
    {
    "id": 29,
    "question": "Which team scored the most goals from the 90th minute onward, and how many did they score?",
    "query": "SELECT\
                team,\
                COUNT(*) AS late_goals\
                FROM {table_name}\
                WHERE event_type = 'goal'\
                AND minute >= 90\
                GROUP BY team\
                HAVING COUNT(*) = (\
                SELECT MAX(g_in_late)\
                FROM (\
                    SELECT COUNT(*) AS g_in_late\
                    FROM {table_name}\
                    WHERE event_type = 'goal'\
                    AND minute >= 90\
                    GROUP BY team\
                ) t\
                );",
    "exp": "Filter goal events to minute >= 90 (stoppage or very late time), count them per team, and return the team or teams with the most late goals.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team was most dangerous in stoppage time (after the 90th minute)?",
        "Show the team that scored the most very late goals.",
        "Who dominated the dying minutes in terms of goals scored?"
    ],
    "primary_key": "team"
    },
    {
    "id": 30,
    "question": "Which players scored more than one goal in the match, and how many goals did each of them score?",
    "query": "SELECT\
                player,\
                COUNT(*) AS total_goals\
                FROM {table_name}\
                WHERE event_type = 'goal'\
                GROUP BY player\
                HAVING COUNT(*) > 1\
                ORDER BY total_goals DESC, player ASC;",
    "exp": "Consider only goal events, group them by player, keep players with at least two goals, and list them ordered by goal count.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who scored multiple goals (braces, hat-tricks, etc.) in the match?",
        "List all players who found the net more than once and their goal totals.",
        "Show multi-goal scorers and how many goals they scored."
    ],
    "primary_key": "player"
    },
    {
    "id": 31,
    "question": "How many goals did {team} score {temporal_phrase}?",
    "query": "SELECT \
                COUNT(*) AS total_goals_team \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND event_type = 'goal' \
                AND {temporal_predicate};",
    "exp": "Filter goal events for the specified team within the time range defined by {temporal_predicate}, and count how many goals they scored.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What was the total number of goals scored by {team} {temporal_phrase}?",
        "How many goals did {team} find the net with during {temporal_phrase}?",
        "Give me the goal count for {team} in the period {temporal_phrase}."
    ],
    "primary_key": "team"
    },
    {
    "id": 32,
    "question": "Which player scored the most goals {temporal_phrase}, and how many goals did they score?",
    "query": "SELECT \
                player, \
                COUNT(*) AS total_goals \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                AND {temporal_predicate} \
                GROUP BY player \
                HAVING COUNT(*) = ( \
                SELECT MAX(goals_in_range) \
                FROM ( \
                    SELECT COUNT(*) AS goals_in_range \
                    FROM {table_name} \
                    WHERE event_type = 'goal' \
                    AND {temporal_predicate} \
                    GROUP BY player \
                ) g \
                );",
    "exp": "Within the temporal window defined by {temporal_predicate}, count goals per player and return the player or players with the highest tally.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Who was the top scorer {temporal_phrase}?",
        "Which player had the most goals in the period {temporal_phrase}?",
        "Show the player with the highest goal count {temporal_phrase}, and how many they scored."
    ],
    "primary_key": "player"
    },
    {
    "id": 33,
    "question": "Which team committed the most fouls {temporal_phrase}, and how many fouls did they commit?",
    "query": "SELECT \
                team, \
                COUNT(*) AS total_fouls \
                FROM {table_name} \
                WHERE event_type = 'foul' \
                AND {temporal_predicate} \
                GROUP BY team \
                HAVING COUNT(*) = ( \
                SELECT MAX(fouls_in_range) \
                FROM ( \
                    SELECT COUNT(*) AS fouls_in_range \
                    FROM {table_name} \
                    WHERE event_type = 'foul' \
                    AND {temporal_predicate} \
                    GROUP BY team \
                ) f \
                );",
    "exp": "Restrict to foul events inside the time interval defined by {temporal_predicate}, count them for each team, and return the team(s) with the most fouls.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Which team fouled the most {temporal_phrase}?",
        "Show the team with the highest foul count during {temporal_phrase}.",
        "Who was the most foul-heavy side in the period {temporal_phrase}?"
    ],
    "primary_key": "team"
    },
    {
    "id": 34,
    "question": "How many yellow cards did each team receive {temporal_phrase}?",
    "query": "SELECT \
                team, \
                COUNT(*) AS yellow_cards \
                FROM {table_name} \
                WHERE event_type = 'yellow card' \
                AND {temporal_predicate} \
                GROUP BY team \
                ORDER BY yellow_cards DESC, team ASC;",
    "exp": "Filter to yellow card events within the temporal window, group them by team, and count how many yellow cards each team received.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "During {temporal_phrase}, how many yellow cards did each team get?",
        "List all teams and the number of yellow cards they received {temporal_phrase}.",
        "Provide a breakdown of yellow cards per team for the period {temporal_phrase}."
    ],
    "primary_key": "team"
    },
    {
    "id": 35,
    "question": "Which player was caught offside the most times {temporal_phrase}, and how many offsides did they have?",
    "query": "SELECT \
                player, \
                COUNT(*) AS offsides \
                FROM {table_name} \
                WHERE event_type = 'offside' \
                AND {temporal_predicate} \
                GROUP BY player \
                HAVING COUNT(*) = ( \
                SELECT MAX(os_in_range) \
                FROM ( \
                    SELECT COUNT(*) AS os_in_range \
                    FROM {table_name} \
                    WHERE event_type = 'offside' \
                    AND {temporal_predicate} \
                    GROUP BY player \
                ) o \
                );",
    "exp": "Within the specified temporal window, count offside events per player and return whoever has the highest offside count.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Who was offside the most {temporal_phrase}?",
        "Which player topped the offside chart during {temporal_phrase}?",
        "Show the player with the highest number of offsides {temporal_phrase} and their count."
    ],
    "primary_key": "player"
    },
    {
    "id": 36,
    "question": "How many corner kicks did each team take {temporal_phrase}?",
    "query": "SELECT \
                team, \
                COUNT(*) AS total_corners \
                FROM {table_name} \
                WHERE event_type = 'corner kick' \
                AND {temporal_predicate} \
                GROUP BY team \
                ORDER BY total_corners DESC, team ASC;",
    "exp": "Filter corner kick events to the time window, group by team, and count corners per team.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "During {temporal_phrase}, how many corner kicks did each team take?",
        "List total corners per team in the period {temporal_phrase}.",
        "Show which team had the most corners {temporal_phrase} and the full team breakdown."
    ],
    "primary_key": "team"
    },
    {
    "id": 37,
    "question": "Which player attempted the most shots {temporal_phrase}, and how many shots did they take?",
    "query": "SELECT \
                player, \
                COUNT(*) AS total_shots \
                FROM {table_name} \
                WHERE event_type = 'shot' \
                AND {temporal_predicate} \
                GROUP BY player \
                HAVING COUNT(*) = ( \
                SELECT MAX(shots_in_range) \
                FROM ( \
                    SELECT COUNT(*) AS shots_in_range \
                    FROM {table_name} \
                    WHERE event_type = 'shot' \
                    AND {temporal_predicate} \
                    GROUP BY player \
                ) s \
                );",
    "exp": "Within the temporal range, count pure shot events (excluding separate goal rows if you keep them distinct) per player and return the highest shooter.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Who took the most shots {temporal_phrase}?",
        "Which player was shooting the most often during {temporal_phrase}?",
        "Show the highest shot-attempting player in the timeframe {temporal_phrase}."
    ],
    "primary_key": "player"
    },
    {
    "id": 38,
    "question": "Which players were sent off {temporal_phrase}, and at what minute were they dismissed?",
    "query": "SELECT \
                player, \
                minute \
                FROM {table_name} \
                WHERE event_type IN ('red card', 'sent off') \
                AND {temporal_predicate} \
                ORDER BY minute ASC, player ASC;",
    "exp": "Filter red card / sent off events to the specified temporal window and list each dismissal with the player name and minute.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Who was sent off {temporal_phrase}, and when?",
        "List all red-card or sent-off incidents during {temporal_phrase}.",
        "Show the dismissed players {temporal_phrase} along with the dismissal minute."
    ],
    "primary_key": ["player", "minute"]
    },
    {
    "id": 39,
    "question": "For each team, how many fouls, yellow cards, and red/sent-off incidents occurred {temporal_phrase}?",
    "query": "SELECT \
                team, \
                SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls, \
                SUM(CASE WHEN event_type = 'yellow card' THEN 1 ELSE 0 END) AS yellow_cards, \
                SUM(CASE WHEN event_type IN ('red card','sent off') THEN 1 ELSE 0 END) AS red_cards \
                FROM {table_name} \
                WHERE {temporal_predicate} \
                GROUP BY team \
                ORDER BY fouls DESC, yellow_cards DESC, red_cards DESC, team ASC;",
    "exp": "Within the temporal range, aggregate disciplinary events (fouls and cards) per team and sort by foul and card counts.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "During {temporal_phrase}, what was the foul and card record for each team?",
        "Show fouls, yellow cards, and red cards per team in the period {temporal_phrase}.",
        "Give a disciplinary summary per team {temporal_phrase}."
    ],
    "primary_key": "team"
    },
    {
    "id": 40,
    "question": "Which minute {temporal_phrase} had the highest total number of key events, and how many events occurred?",
    "query": "WITH per_minute AS ( \
                SELECT \
                    minute, \
                    COUNT(*) AS total_events \
                FROM {table_name} \
                WHERE event_type IN ('shot','goal','foul','yellow card','red card','sent off','offside','corner kick','free kick') \
                    AND {temporal_predicate} \
                GROUP BY minute \
                ), \
                mx AS (SELECT MAX(total_events) AS max_events FROM per_minute) \
                SELECT \
                minute, \
                total_events \
                FROM per_minute \
                WHERE total_events = (SELECT max_events FROM mx);",
    "exp": "Restrict to the given time window and key event types, count events per minute, and return the minute(s) with the maximum combined event count.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "In the period {temporal_phrase}, which minute was the most eventful?",
        "Show the minute {temporal_phrase} with the highest number of key events (shots, goals, fouls, cards, etc.).",
        "Find the busiest minute {temporal_phrase} and how many events it contained."
    ],
    "primary_key": "minute"
    },
    {
    "id": 41,
    "question": "Which player from {team} scored the most goals {temporal_phrase}, and how many goals did they score?",
    "query": "SELECT \
                player, \
                COUNT(*) AS total_goals \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND event_type = 'goal' \
                AND {temporal_predicate} \
                GROUP BY player \
                HAVING COUNT(*) = ( \
                SELECT MAX(goals_in_range) \
                FROM ( \
                    SELECT COUNT(*) AS goals_in_range \
                    FROM {table_name} \
                    WHERE team = '{team}' \
                    AND event_type = 'goal' \
                    AND {temporal_predicate} \
                    GROUP BY player \
                ) g \
                );",
    "exp": "Within the specified temporal window, restrict to the given team, count goals per player, and return the player or players who scored the most.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "For {team}, which player scored the most goals {temporal_phrase}?",
        "During {temporal_phrase}, who was the top scorer for {team} and how many did they score?",
        "Show the leading goal scorer from {team} in the period {temporal_phrase}."
    ],
    "primary_key": "player"
    },
    {
    "id": 42,
    "question": "How many shots and goals did {player} have {temporal_phrase}?",
    "query": "SELECT \
                SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS total_goals \
                FROM {table_name} \
                WHERE player = '{player}' \
                AND {temporal_predicate};",
    "exp": "Within the given temporal range, count all shot attempts (both 'shot' and 'goal') and all goals for the specified player.",
    "variables": ["table_name", "player", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What are {player}'s shots and goals tally {temporal_phrase}?",
        "How many times did {player} shoot and how many of those were goals during {temporal_phrase}?",
        "Give the number of shots and goals for {player} in the period {temporal_phrase}."
    ],
    "primary_key": "player"
    },
    {
    "id": 43,
    "question": "For each team, what were their total shots, goals, and goal conversion rate {temporal_phrase}?",
    "query": "WITH per_team AS ( \
                SELECT \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots, \
                    SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS total_goals \
                FROM {table_name} \
                WHERE {temporal_predicate} \
                GROUP BY team \
                ) \
                SELECT \
                team, \
                total_shots, \
                total_goals, \
                ROUND((total_goals * 100.0) / NULLIF(total_shots, 0), 2) AS conversion_percentage \
                FROM per_team \
                ORDER BY conversion_percentage DESC, total_goals DESC, team ASC;",
    "exp": "Within the temporal window, aggregate shots and goals per team and compute their goal conversion percentage (goals as a percentage of total shots).",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "During {temporal_phrase}, how did each team perform in terms of shots, goals, and conversion rate?",
        "Show shots, goals, and goal conversion percentage per team {temporal_phrase}.",
        "List each team's shooting output and efficiency in the period {temporal_phrase}."
    ],
    "primary_key": "team"
    },
    {
    "id": 44,
    "question": "For team {team}, how many fouls did each of their players commit {temporal_phrase}?",
    "query": "SELECT \
                player, \
                COUNT(*) AS fouls_committed \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND event_type = 'foul' \
                AND {temporal_predicate} \
                GROUP BY player \
                ORDER BY fouls_committed DESC, player ASC;",
    "exp": "Restrict to the given team and time window, filter foul events, and count fouls per player.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Which players from {team} committed fouls {temporal_phrase}, and how many each?",
        "Show a list of {team}'s players with their foul counts in the period {temporal_phrase}.",
        "During {temporal_phrase}, how many fouls did each player from {team} concede?"
    ],
    "primary_key": "player"
    },
    {
    "id": 45,
    "question": "How many yellow and red cards did each player from {team} receive {temporal_phrase}?",
    "query": "SELECT \
                player, \
                SUM(CASE WHEN event_type = 'yellow card' THEN 1 ELSE 0 END) AS yellow_cards, \
                SUM(CASE WHEN event_type IN ('red card','sent off') THEN 1 ELSE 0 END) AS red_cards \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND {temporal_predicate} \
                GROUP BY player \
                HAVING yellow_cards > 0 OR red_cards > 0 \
                ORDER BY red_cards DESC, yellow_cards DESC, player ASC;",
    "exp": "Within the temporal window and specified team, count yellow and red/sent-off events per player and keep only players who received at least one card.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Which players from {team} were booked or sent off {temporal_phrase}, and how many cards did each get?",
        "Show yellow and red card counts per player for {team} during {temporal_phrase}.",
        "List all carded players from {team} in the period {temporal_phrase}."
    ],
    "primary_key": "player"
    },
    {
    "id": 46,
    "question": "For each team, how many goals did they score within 2 minutes after a corner kick or free kick {temporal_phrase}?",
    "query": "WITH set_pieces AS ( \
                SELECT minute AS sp_minute, team \
                FROM {table_name} \
                WHERE event_type IN ('corner kick','free kick') \
                    AND {temporal_predicate} \
                ), \
                goals AS ( \
                SELECT minute AS goal_minute, team \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                ) \
                SELECT \
                sp.team, \
                COUNT(*) AS goals_after_set_piece \
                FROM set_pieces sp \
                JOIN goals g \
                ON g.team = sp.team \
                AND g.goal_minute > sp.sp_minute \
                AND g.goal_minute <= sp.sp_minute + 2 \
                GROUP BY sp.team \
                ORDER BY goals_after_set_piece DESC, sp.team ASC;",
    "exp": "Within the temporal window, take all corner/free kick events per team and count how many goals that team scored within the following 2 minutes, regardless of whether the goal event itself is strictly inside the temporal range.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "During {temporal_phrase}, how many goals did each team score shortly (within 2 minutes) after a corner or free kick?",
        "Show set-piece effectiveness {temporal_phrase} in terms of goals within 2 minutes by team.",
        "Which teams turned set pieces into quick goals in the period {temporal_phrase}?"
    ],
    "primary_key": "team"
    },
    {
    "id": 47,
    "question": "Which team had the most total shots in the entire match, and how many of their shots came {temporal_phrase}?",
    "query": "WITH team_totals AS ( \
                SELECT \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots \
                FROM {table_name} \
                GROUP BY team \
                ), \
                top_teams AS ( \
                SELECT team \
                FROM team_totals \
                WHERE total_shots = ( \
                    SELECT MAX(total_shots) FROM team_totals \
                ) \
                ), \
                shots_in_range AS ( \
                SELECT \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') AND {temporal_predicate} THEN 1 ELSE 0 END) AS shots_in_temporal_range \
                FROM {table_name} \
                WHERE team IN (SELECT team FROM top_teams) \
                GROUP BY team \
                ) \
                SELECT \
                t.team, \
                t.total_shots, \
                s.shots_in_temporal_range \
                FROM team_totals t \
                JOIN shots_in_range s \
                ON t.team = s.team \
                WHERE t.team IN (SELECT team FROM top_teams);",
    "exp": "First find the team(s) with the most total shots across the full match, then for those team(s) count how many of their shot attempts occurred within the temporal window.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Which overall highest-shooting team, and how many of their shots were taken {temporal_phrase}?",
        "For the team with the most shots in the match, show how many shots they took during {temporal_phrase}.",
        "Identify the top shooting team and their shot count in the period {temporal_phrase}."
    ],
    "primary_key": "team"
    },
    {
    "id": 48,
    "question": "Which player had the most total shots in the match, and how many of their shots came {temporal_phrase}?",
    "query": "WITH player_totals AS ( \
                SELECT \
                    player, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots \
                FROM {table_name} \
                GROUP BY player \
                ), \
                top_players AS ( \
                SELECT player \
                FROM player_totals \
                WHERE total_shots = ( \
                    SELECT MAX(total_shots) FROM player_totals \
                ) \
                ), \
                shots_in_range AS ( \
                SELECT \
                    player, \
                    SUM(CASE WHEN event_type IN ('shot','goal') AND {temporal_predicate} THEN 1 ELSE 0 END) AS shots_in_temporal_range \
                FROM {table_name} \
                WHERE player IN (SELECT player FROM top_players) \
                GROUP BY player \
                ) \
                SELECT \
                p.player, \
                p.total_shots, \
                s.shots_in_temporal_range \
                FROM player_totals p \
                JOIN shots_in_range s \
                ON p.player = s.player \
                WHERE p.player IN (SELECT player FROM top_players);",
    "exp": "Identify the player(s) with the highest total shot attempts in the whole match, then count how many of those shots occurred in the given temporal window.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Who shot the most overall, and how many shots did they take {temporal_phrase}?",
        "For the player with the most shot attempts in the match, show their shot count in the period {temporal_phrase}.",
        "Identify the top shooter and the number of shots they took during {temporal_phrase}."
    ],
    "primary_key": "player"
    },
    {
    "id": 49,
    "question": "What was the shot conversion rate (goals per shot) for {player} {temporal_phrase}?",
    "query": "WITH stats AS ( \
                SELECT \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots, \
                    SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS total_goals \
                FROM {table_name} \
                WHERE player = '{player}' \
                    AND {temporal_predicate} \
                ) \
                SELECT \
                total_shots, \
                total_goals, \
                ROUND((total_goals * 100.0) / NULLIF(total_shots, 0), 2) AS conversion_percentage \
                FROM stats;",
    "exp": "Within the temporal window, compute how many shots (including goals) and how many goals {player} had, and derive their goal-per-shot percentage.",
    "variables": ["table_name", "player", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What was {player}'s finishing efficiency {temporal_phrase}?",
        "During {temporal_phrase}, what percentage of {player}'s shots resulted in goals?",
        "Show {player}'s shots, goals, and goal conversion rate in the period {temporal_phrase}."
    ],
    "primary_key": "player"
    },
    {
    "id": 50,
    "question": "For each team, what percentage of their total goals were scored {temporal_phrase}?",
    "query": "WITH team_totals AS ( \
                SELECT \
                    team, \
                    COUNT(*) AS total_goals \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                GROUP BY team \
                ), \
                team_in_range AS ( \
                SELECT \
                    team, \
                    COUNT(*) AS goals_in_range \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                    AND {temporal_predicate} \
                GROUP BY team \
                ) \
                SELECT \
                tt.team, \
                tt.total_goals, \
                COALESCE(tr.goals_in_range, 0) AS goals_in_temporal_range, \
                ROUND( \
                    COALESCE(tr.goals_in_range, 0) * 100.0 / NULLIF(tt.total_goals, 0), \
                    2 \
                ) AS percentage_goals_in_range \
                FROM team_totals tt \
                LEFT JOIN team_in_range tr \
                ON tt.team = tr.team \
                ORDER BY percentage_goals_in_range DESC, tt.team ASC;",
    "exp": "First compute each team's total goals over the whole match, then compute how many of those were scored in the temporal window, and express that as a percentage of their total goals.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What share of each team's total goals came {temporal_phrase}?",
        "For every team, show how many of their goals were scored during {temporal_phrase} and what percentage that represents.",
        "List teams with the fraction of their total goals that occurred in the period {temporal_phrase}."
    ],
    "primary_key": "team"
    },
    {
    "id": 51,
    "question": "Which team had the highest 'red zone occupation ratio'? We define a team’s red zone occupation as the proportion of its attacking events that are explicitly described as being in or near the penalty box. For each team, we count: (A) all attacking events with event_type in ('shot', 'goal', 'corner kick', 'free kick'), and (B) among those, the subset where the description text (case-insensitive) contains the word 'box' (e.g., 'penalty box', 'into the box'). The red zone occupation ratio is B divided by A. Return the team(s) with the highest ratio, as well as their total attacking events and red-zone events.",
    "query": "WITH attacking AS (\
                SELECT\
                    team,\
                    COUNT(*) AS total_attacking,\
                    SUM(CASE WHEN LOWER(description) LIKE '%box%' THEN 1 ELSE 0 END) AS red_zone_events\
                FROM {table_name}\
                WHERE event_type IN ('shot','goal','corner kick','free kick')\
                GROUP BY team\
                ),\
                ratios AS (\
                SELECT\
                    team,\
                    total_attacking,\
                    red_zone_events,\
                    (red_zone_events * 1.0) / NULLIF(total_attacking, 0) AS ratio_exact,\
                    ROUND((red_zone_events * 1.0) / NULLIF(total_attacking, 0), 4) AS red_zone_ratio\
                FROM attacking\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                team,\
                total_attacking,\
                red_zone_events,\
                red_zone_ratio\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Treat 'shot', 'goal', 'corner kick', and 'free kick' as attacking events. For each team, count all such events (A) and how many of them mention 'box' in the description (B). Compute B/A as the red zone occupation ratio, then return the team or teams with the highest ratio along with A and B.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team spent the largest share of its attacking actions in or around the penalty box according to the descriptions?",
        "Identify the team whose attacking events were most often described as happening in the box.",
        "Show the team with the highest proportion of box-related attacking events, plus their counts."
    ],
    "primary_key": "team"
    },
    {
    "id": 52,
    "question": "Which team had the highest 'wide threat ratio'? We define a team’s wide threat ratio as the proportion of its attacking events that are explicitly described as happening on the wings. For each team, we count: (A) all attacking events with event_type in ('shot', 'goal', 'corner kick', 'free kick'), and (B) among those, the subset where the description text (case-insensitive) contains phrases like 'left wing', 'right wing', 'flank', or 'wide'. The wide threat ratio is B divided by A. Return the team(s) with the highest ratio, along with their total attacking events and wide attacks.",
    "query": "WITH attacking AS (\
                SELECT\
                    team,\
                    COUNT(*) AS total_attacking,\
                    SUM(CASE\
                        WHEN LOWER(description) LIKE '%left wing%'\
                            OR LOWER(description) LIKE '%right wing%'\
                            OR LOWER(description) LIKE '%flank%'\
                            OR LOWER(description) LIKE '%wide%'\
                        THEN 1 ELSE 0 END) AS wide_events\
                FROM {table_name}\
                WHERE event_type IN ('shot','goal','corner kick','free kick')\
                GROUP BY team\
                ),\
                ratios AS (\
                SELECT\
                    team,\
                    total_attacking,\
                    wide_events,\
                    (wide_events * 1.0) / NULLIF(total_attacking, 0) AS ratio_exact,\
                    ROUND((wide_events * 1.0) / NULLIF(total_attacking, 0), 4) AS wide_threat_ratio\
                FROM attacking\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                team,\
                total_attacking,\
                wide_events,\
                wide_threat_ratio\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Take all attacking events (shots, goals, corners, free kicks) per team, count how many are described as being on the wing, compute the share of wing events, and select the team(s) with the highest share.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team relied most heavily on wing-based attacks according to the commentary?",
        "Identify the team whose attacking events were most frequently described as coming from the left or right wing.",
        "Show the team with the highest proportion of wide attacks and their counts."
    ],
    "primary_key": "team"
    },
    {
    "id": 53,
    "question": "Which team had the highest 'counter-attack efficiency'? For each team we consider all attacking events with event_type in ('shot', 'goal') where the description text (case-insensitive) contains 'counter', 'counter-attack', or 'fast break'. Among these, let: (A) be the total number of such counter-attacking shots, and (B) be the subset where event_type = 'goal'. The counter-attack efficiency is B divided by A. Return the team(s) with the highest efficiency, along with A (counter shots) and B (counter goals).",
    "query": "WITH counters AS (\
                SELECT\
                    team,\
                    event_type\
                FROM {table_name}\
                WHERE event_type IN ('shot','goal')\
                    AND (LOWER(description) LIKE '%counter%'\
                    OR LOWER(description) LIKE '%counter-attack%'\
                    OR LOWER(description) LIKE '%fast break%')\
                ),\
                per_team AS (\
                SELECT\
                    team,\
                    COUNT(*) AS counter_shots,\
                    SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS counter_goals\
                FROM counters\
                GROUP BY team\
                ),\
                ratios AS (\
                SELECT\
                    team,\
                    counter_shots,\
                    counter_goals,\
                    (counter_goals * 1.0) / NULLIF(counter_shots, 0) AS ratio_exact,\
                    ROUND((counter_goals * 1.0) / NULLIF(counter_shots, 0), 4) AS counter_attack_efficiency\
                FROM per_team\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                team,\
                counter_shots,\
                counter_goals,\
                counter_attack_efficiency\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Filter shots and goals whose descriptions mention counter-attacks or fast breaks, aggregate them per team, compute goals divided by total such attempts, and return the team(s) with the highest counter-attack efficiency.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team was most efficient at turning counter-attacking shots into goals?",
        "Show the team that converted the highest share of its counter-attacking attempts into goals.",
        "Identify the side with the best counter-attack goal rate, plus their counter shots and goals."
    ],
    "primary_key": "team"
    },
    {
    "id": 54,
    "question": "Which team had the best 'set-piece goal conversion rate'? We define set-piece events as those with event_type in ('free kick', 'corner kick'). For each team, we count: (A) all such set-piece events, and (B) the distinct set-piece events where that team scored a goal within the next 2 minutes (event_type = 'goal' for the same team and minute between set-piece minute + 0 and +2). The set-piece goal conversion rate is B divided by A. Return the team(s) with the highest rate, and include their A and B counts.",
    "query": "WITH set_pieces AS (\
                SELECT minute AS sp_minute, team\
                FROM {table_name}\
                WHERE event_type IN ('free kick','corner kick')\
                ),\
                goals AS (\
                SELECT minute AS goal_minute, team\
                FROM {table_name}\
                WHERE event_type = 'goal'\
                ),\
                linked AS (\
                SELECT\
                    sp.team,\
                    sp.sp_minute,\
                    COUNT(*) AS goals_after_sp\
                FROM set_pieces sp\
                JOIN goals g\
                    ON g.team = sp.team\
                AND g.goal_minute > sp.sp_minute\
                AND g.goal_minute <= sp.sp_minute + 2\
                GROUP BY sp.team, sp.sp_minute\
                ),\
                per_team AS (\
                SELECT\
                    sp.team,\
                    COUNT(*) AS total_set_pieces,\
                    COUNT(DISTINCT l.sp_minute) AS set_pieces_leading_to_goal\
                FROM set_pieces sp\
                LEFT JOIN linked l\
                    ON sp.team = l.team\
                AND sp.sp_minute = l.sp_minute\
                GROUP BY sp.team\
                ),\
                ratios AS (\
                SELECT\
                    team,\
                    total_set_pieces,\
                    set_pieces_leading_to_goal,\
                    (set_pieces_leading_to_goal * 1.0) / NULLIF(total_set_pieces, 0) AS ratio_exact,\
                    ROUND((set_pieces_leading_to_goal * 1.0) / NULLIF(total_set_pieces, 0), 4) AS set_piece_conversion_rate\
                FROM per_team\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                team,\
                total_set_pieces,\
                set_pieces_leading_to_goal,\
                set_piece_conversion_rate\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Treat free kicks and corners as set pieces. For each team, count all such events and how many of them are followed by a goal for the same team within 2 minutes, compute the conversion rate, and return the team(s) with the highest value.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team was best at turning corners and free kicks into goals within a short window?",
        "Show the team with the highest set-piece goal conversion rate and their relevant counts.",
        "Identify the most effective team from set pieces based on quick goals after them."
    ],
    "primary_key": "team"
    },
    {
    "id": 55,
    "question": "Which team showed the highest 'aerial dominance in the box'? For each team, we look at all events with event_type in ('shot', 'goal', 'free kick', 'corner kick') where the description contains any of 'header', 'headed', or 'headed effort' and also contains 'box' or 'penalty area'. Let (A) be the total number of such aerial box attempts, and (B) the subset where event_type = 'goal'. The aerial box conversion ratio is B divided by A. Return each team’s A, B, and conversion ratio, and identify the team(s) with the highest ratio.",
    "query": "WITH aerial AS (\
                SELECT\
                    team,\
                    event_type\
                FROM {table_name}\
                WHERE event_type IN ('shot','goal','free kick','corner kick')\
                    AND (LOWER(description) LIKE '%header%'\
                    OR LOWER(description) LIKE '%headed%'\
                    OR LOWER(description) LIKE '%headed effort%')\
                    AND (LOWER(description) LIKE '%box%'\
                    OR LOWER(description) LIKE '%penalty area%')\
                ),\
                per_team AS (\
                SELECT\
                    team,\
                    COUNT(*) AS aerial_box_attempts,\
                    SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS aerial_box_goals\
                FROM aerial\
                GROUP BY team\
                ),\
                ratios AS (\
                SELECT\
                    team,\
                    aerial_box_attempts,\
                    aerial_box_goals,\
                    (aerial_box_goals * 1.0) / NULLIF(aerial_box_attempts, 0) AS ratio_exact,\
                    ROUND((aerial_box_goals * 1.0) / NULLIF(aerial_box_attempts, 0), 4) AS aerial_box_conversion_ratio\
                FROM per_team\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                team,\
                aerial_box_attempts,\
                aerial_box_goals,\
                aerial_box_conversion_ratio\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Filter attacking events described as headers in or around the box, count them per team, compute the fraction that became goals, and pick the team(s) with the best aerial finishing in the box.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team was most effective with headed chances in the box?",
        "Show teams' header-based attempts in the penalty area and which converted the best.",
        "Identify the side with the best aerial conversion rate in box-related situations."
    ],
    "primary_key": "team"
    },
    {
    "id": 56,
    "question": "Which team had the highest 'dangerous free kick ratio'? For each team, we consider all events with event_type = 'free kick'. Among these, (A) is the count of all free kicks, and (B) is the subset where the description text contains 'edge of the box', 'dangerous position', 'central area', or 'just outside the box'. The dangerous free kick ratio is B divided by A. Return the team(s) with the highest ratio, including their A and B values.",
    "query": "WITH fk AS (\
                SELECT\
                    team,\
                    description\
                FROM {table_name}\
                WHERE event_type = 'free kick'\
                ),\
                per_team AS (\
                SELECT\
                    team,\
                    COUNT(*) AS total_free_kicks,\
                    SUM(CASE\
                        WHEN LOWER(description) LIKE '%edge of the box%'\
                            OR LOWER(description) LIKE '%dangerous position%'\
                            OR LOWER(description) LIKE '%central area%'\
                            OR LOWER(description) LIKE '%just outside the box%'\
                        THEN 1 ELSE 0 END) AS dangerous_free_kicks\
                FROM fk\
                GROUP BY team\
                ),\
                ratios AS (\
                SELECT\
                    team,\
                    total_free_kicks,\
                    dangerous_free_kicks,\
                    (dangerous_free_kicks * 1.0) / NULLIF(total_free_kicks, 0) AS ratio_exact,\
                    ROUND((dangerous_free_kicks * 1.0) / NULLIF(total_free_kicks, 0), 4) AS dangerous_free_kick_ratio\
                FROM per_team\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                team,\
                total_free_kicks,\
                dangerous_free_kicks,\
                dangerous_free_kick_ratio\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Look at all free kicks per team, identify those described as being in particularly dangerous central or edge-of-box areas, compute the dangerous share, and select the team(s) with the highest proportion.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team’s free kicks were most often from dangerous locations?",
        "Show the team whose free kicks most frequently came from edge-of-box or central positions.",
        "Identify the side with the highest dangerous free kick ratio."
    ],
    "primary_key": "team"
    },
    {
    "id": 57,
    "question": "Which team forced the most 'press-induced turnovers' leading to shots? We approximate press-induced turnovers as fouls by the opponent where the description text contains words like 'pressed', 'pressure', 'high press', or 'pressed into a mistake'. For each pressing team, (A) is the number of such fouls committed by the opponent that were followed by at least one shot or goal for the pressing team within the next 2 minutes, and (B) is the total number of shots and goals they took in those post-foul windows. The press-induced turnover intensity is B divided by A. Return the team(s) with the highest intensity, with A and B counts.",
    "query": "WITH press_fouls AS (\
                SELECT\
                    minute AS foul_minute,\
                    team AS fouling_team\
                FROM {table_name}\
                WHERE event_type = 'foul'\
                    AND (LOWER(description) LIKE '%pressed%'\
                    OR LOWER(description) LIKE '%pressure%'\
                    OR LOWER(description) LIKE '%high press%'\
                    OR LOWER(description) LIKE '%pressed into a mistake%')\
                ),\
                shots_after AS (\
                SELECT\
                    pf.foul_minute,\
                    pf.fouling_team,\
                    s.team AS pressing_team,\
                    s.minute AS shot_minute\
                FROM press_fouls pf\
                JOIN {table_name} s\
                    ON s.minute > pf.foul_minute\
                AND s.minute <= pf.foul_minute + 2\
                AND s.event_type IN ('shot','goal')\
                AND s.team <> pf.fouling_team\
                ),\
                per_pressing AS (\
                SELECT\
                    pressing_team AS team,\
                    COUNT(DISTINCT foul_minute) AS press_turnovers,\
                    COUNT(*) AS shots_after_turnovers\
                FROM shots_after\
                GROUP BY pressing_team\
                ),\
                ratios AS (\
                SELECT\
                    team,\
                    press_turnovers,\
                    shots_after_turnovers,\
                    (shots_after_turnovers * 1.0) / NULLIF(press_turnovers, 0) AS ratio_exact,\
                    ROUND((shots_after_turnovers * 1.0) / NULLIF(press_turnovers, 0), 4) AS press_induced_turnover_intensity\
                FROM per_pressing\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                team,\
                press_turnovers,\
                shots_after_turnovers,\
                press_induced_turnover_intensity\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Find fouls explicitly described as being caused by pressing. For those fouls, look at shots/goals taken by the other team in the next 2 minutes, treat that team as the pressing side, count how many fouls of this kind led to shots and how many shots they generated, compute B/A, and return the team(s) with the highest intensity.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team most effectively turned press-induced fouls into shooting opportunities?",
        "Show the teams that generated the most shots from pressing turnovers and their intensity ratio.",
        "Identify the side with the strongest press-to-shot conversion impact."
    ],
    "primary_key": "team"
    },
    {
    "id": 58,
    "question": "Which player had the highest 'penalty-box shot share' among players with at least 3 shots? For each player, we count: (A) total shots with event_type in ('shot', 'goal'), and (B) among those, the ones where the description text includes 'inside the box', 'six-yard box', or 'penalty box'. The penalty-box shot share is B divided by A. Only consider players with A ≥ 3, and return the player(s) with the highest share, along with A and B.",
    "query": "WITH per_player AS (\
                SELECT\
                    player,\
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots,\
                    SUM(CASE\
                        WHEN event_type IN ('shot','goal')\
                        AND (LOWER(description) LIKE '%inside the box%'\
                            OR LOWER(description) LIKE '%six-yard box%'\
                            OR LOWER(description) LIKE '%penalty box%')\
                        THEN 1 ELSE 0 END) AS box_shots\
                FROM {table_name}\
                GROUP BY player\
                HAVING SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) >= 3\
                ),\
                ratios AS (\
                SELECT\
                    player,\
                    total_shots,\
                    box_shots,\
                    (box_shots * 1.0) / NULLIF(total_shots, 0) AS ratio_exact,\
                    ROUND((box_shots * 1.0) / NULLIF(total_shots, 0), 4) AS penalty_box_shot_share\
                FROM per_player\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                player,\
                total_shots,\
                box_shots,\
                penalty_box_shot_share\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "For each player with at least 3 shots, compute how many of their shot attempts were explicitly described as being taken from inside or within the penalty area, then find the player(s) whose share of such shots is the highest.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player focused most on shooting from inside the penalty area, given a minimum of 3 shots?",
        "Show players with at least 3 shots and identify who had the largest share from box locations.",
        "Identify the attacker whose shot profile was most heavily concentrated inside the box."
    ],
    "primary_key": "player"
    },
    {
    "id": 59,
    "question": "Which player was the most 'long-range oriented shooter'? For each player, consider events with event_type in ('shot', 'goal') where the description text contains any of 'long range', 'from distance', 'from outside the box', or 'from 25 yards'. Let (A) be that player’s total shots (all 'shot' + 'goal'), and (B) the number of long-range attempts. The long-range shooter index is B divided by A. Return the player(s) with the highest index, along with their A and B values.",
    "query": "WITH per_player AS (\
                SELECT\
                    player,\
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS total_shots,\
                    SUM(CASE\
                        WHEN event_type IN ('shot','goal')\
                        AND (LOWER(description) LIKE '%long range%'\
                            OR LOWER(description) LIKE '%from distance%'\
                            OR LOWER(description) LIKE '%from outside the box%'\
                            OR LOWER(description) LIKE '%from 25 yards%')\
                        THEN 1 ELSE 0 END) AS long_range_shots\
                FROM {table_name}\
                GROUP BY player\
                HAVING SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) > 0\
                ),\
                ratios AS (\
                SELECT\
                    player,\
                    total_shots,\
                    long_range_shots,\
                    (long_range_shots * 1.0) / NULLIF(total_shots, 0) AS ratio_exact,\
                    ROUND((long_range_shots * 1.0) / NULLIF(total_shots, 0), 4) AS long_range_shooter_index\
                FROM per_player\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                player,\
                total_shots,\
                long_range_shots,\
                long_range_shooter_index\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Count how many of each player’s shots and goals are described as long-range attempts, compute the proportion of long-range efforts per player, and identify the player(s) with the highest proportion.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player most frequently shoots from long distance relative to all their attempts?",
        "Show the player whose shots are most biased toward long-range efforts.",
        "Identify the player with the highest share of long-range shots among their total attempts."
    ],
    "primary_key": "player"
    },
    {
    "id": 60,
    "question": "Which team showed the worst 'discipline under pressure'? For each team, we first consider fouls committed by that team (event_type = 'foul'). We then check whether within the next 1 minute there is a card event (event_type in ('yellow card', 'red card', 'sent off')) given to the same team where the description text includes 'persistent', 'reckless', 'dangerous', or 'late challenge'. Let (A) be the total fouls committed by the team and (B) the number of such carded incidents following fouls. The discipline under pressure ratio is B divided by A. Return the team(s) with the highest ratio and their A/B counts.",
    "query": "WITH fouls AS (\
                SELECT\
                    minute AS foul_minute,\
                    team\
                FROM {table_name}\
                WHERE event_type = 'foul'\
                ),\
                cards AS (\
                SELECT\
                    minute AS card_minute,\
                    team,\
                    description\
                FROM {table_name}\
                WHERE event_type IN ('yellow card','red card','sent off')\
                ),\
                linked AS (\
                SELECT\
                    f.team,\
                    f.foul_minute,\
                    COUNT(*) AS card_incidents\
                FROM fouls f\
                JOIN cards c\
                    ON c.team = f.team\
                AND c.card_minute > f.foul_minute\
                AND c.card_minute <= f.foul_minute + 1\
                AND (LOWER(c.description) LIKE '%persistent%'\
                    OR LOWER(c.description) LIKE '%reckless%'\
                    OR LOWER(c.description) LIKE '%dangerous%'\
                    OR LOWER(c.description) LIKE '%late challenge%')\
                GROUP BY f.team, f.foul_minute\
                ),\
                per_team AS (\
                SELECT\
                    f.team,\
                    COUNT(*) AS total_fouls,\
                    COALESCE(COUNT(DISTINCT l.foul_minute), 0) AS discipline_incidents\
                FROM fouls f\
                LEFT JOIN linked l\
                    ON f.team = l.team\
                AND f.foul_minute = l.foul_minute\
                GROUP BY f.team\
                ),\
                ratios AS (\
                SELECT\
                    team,\
                    total_fouls,\
                    discipline_incidents,\
                    (discipline_incidents * 1.0) / NULLIF(total_fouls, 0) AS ratio_exact,\
                    ROUND((discipline_incidents * 1.0) / NULLIF(total_fouls, 0), 4) AS discipline_under_pressure_ratio\
                FROM per_team\
                ),\
                worst AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                team,\
                total_fouls,\
                discipline_incidents,\
                discipline_under_pressure_ratio\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM worst);",
    "exp": "Treat fouls as pressure moments for the defending team, then check whether they quickly receive discipline-related cards as described. Compute how often fouls are followed by these cards, and return the team(s) with the highest such ratio.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team most frequently followed fouls with reckless or persistent card incidents shortly after?",
        "Show the side with the worst discipline when under pressure from fouls leading to quick cards.",
        "Identify the team where fouls most often resulted in serious disciplinary cards soon after."
    ],
    "primary_key": "team"
    },
    {
    "id": 61,
    "question": "Which team had the largest 'momentum-changing event ratio'? We treat momentum-changing events as goals or red-card/sent-off events where the description text contains 'turnaround', 'shift', 'swing', 'crucial', or 'decisive'. For each team, (A) is the total number of events with event_type in ('goal', 'red card', 'sent off'), and (B) is the subset where the description contains those momentum-related keywords. The momentum-changing event ratio is B divided by A. Return the team(s) with the highest ratio, with A and B counts.",
    "query": "WITH events AS (\
                SELECT\
                    team,\
                    event_type,\
                    description\
                FROM {table_name}\
                WHERE event_type IN ('goal','red card','sent off')\
                ),\
                per_team AS (\
                SELECT\
                    team,\
                    COUNT(*) AS total_big_events,\
                    SUM(CASE\
                        WHEN LOWER(description) LIKE '%turnaround%'\
                            OR LOWER(description) LIKE '%shift%'\
                            OR LOWER(description) LIKE '%swing%'\
                            OR LOWER(description) LIKE '%crucial%'\
                            OR LOWER(description) LIKE '%decisive%'\
                        THEN 1 ELSE 0 END) AS momentum_events\
                FROM events\
                GROUP BY team\
                ),\
                ratios AS (\
                SELECT\
                    team,\
                    total_big_events,\
                    momentum_events,\
                    (momentum_events * 1.0) / NULLIF(total_big_events, 0) AS ratio_exact,\
                    ROUND((momentum_events * 1.0) / NULLIF(total_big_events, 0), 4) AS momentum_changing_event_ratio\
                FROM per_team\
                ),\
                best AS (\
                SELECT MAX(ratio_exact) AS max_ratio FROM ratios\
                )\
                SELECT\
                team,\
                total_big_events,\
                momentum_events,\
                momentum_changing_event_ratio\
                FROM ratios\
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Look at major match-turning events (goals, red cards, and sendings off) per team, identify those explicitly described as crucial or decisive in the commentary, compute how large a share they are of all big events, and return the team(s) with the highest share.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team had the biggest share of crucial or decisive goals and red-card events?",
        "Show the team whose big events were most often described as turning points in the match.",
        "Identify the side with the highest ratio of momentum-shifting goals and cards."
    ],
    "primary_key": "team"
    },
    {
    "id": 62,
    "question": "Which team had the highest goal creation chain efficiency? A chain is defined as free kick → shot → goal within 3 minutes. For each team: (A) free kicks, (B) those leading to a shot within 2 minutes, (C) those where a goal occurred within 3 minutes of the free kick. Efficiency = C/B.",
    "query": "WITH fk AS ( \
                SELECT minute AS fk_minute, team \
                FROM {table_name} \
                WHERE event_type = 'free kick' \
                ), \
                shots AS ( \
                SELECT minute AS shot_minute, team \
                FROM {table_name} \
                WHERE event_type IN ('shot','goal') \
                ), \
                goals AS ( \
                SELECT minute AS goal_minute, team \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                ), \
                fk_to_shot AS ( \
                SELECT f.team, f.fk_minute \
                FROM fk f \
                JOIN shots s \
                    ON s.team = f.team \
                AND s.shot_minute > f.fk_minute \
                AND s.shot_minute <= f.fk_minute + 2 \
                ), \
                fk_to_goal AS ( \
                SELECT f.team, f.fk_minute \
                FROM fk f \
                JOIN goals g \
                    ON g.team = f.team \
                AND g.goal_minute > f.fk_minute \
                AND g.goal_minute <= f.fk_minute + 3 \
                ), \
                per_team AS ( \
                SELECT \
                    fk.team, \
                    COUNT(*) AS total_fk, \
                    (SELECT COUNT(*) FROM fk_to_shot WHERE fk_to_shot.team = fk.team) AS shot_links, \
                    (SELECT COUNT(DISTINCT fk_minute) FROM fk_to_goal WHERE fk_to_goal.team = fk.team) AS goal_links \
                FROM fk \
                GROUP BY fk.team \
                ), \
                ratios AS ( \
                SELECT \
                    team, \
                    total_fk, \
                    shot_links, \
                    goal_links, \
                    (goal_links * 1.0) / NULLIF(shot_links, 0) AS ratio_exact, \
                    ROUND((goal_links * 1.0) / NULLIF(shot_links, 0), 4) AS chain_efficiency \
                FROM per_team \
                ), \
                best AS (SELECT MAX(ratio_exact) AS max_ratio FROM ratios) \
                SELECT team, total_fk, shot_links, goal_links, chain_efficiency \
                FROM ratios \
                WHERE ratio_exact = (SELECT max_ratio FROM best);",
    "exp": "Detect sequences where a free kick produces a shot within 2 minutes and a goal within 3 minutes. Compute chain efficiency (goals from shot-linked free kicks). Return the team with highest chain efficiency.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team converted the most free kicks into shot→goal sequences?",
        "Identify the team with the most effective free-kick-to-goal chains.",
        "Show the best team at turning free kicks into goals within a short sequence."
    ],
    "primary_key": "team"
    },
    {
    "id": 63,
    "question": "List all players with their total shots, goals, and goal conversion rate.",
    "query": "SELECT \
                player, \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END) AS total_shots, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS total_goals, \
                ROUND( \
                    (SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) * 100.0) \
                    / NULLIF(SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END), 0), \
                    2 \
                ) AS goal_conversion_percentage \
                FROM {table_name} \
                GROUP BY player \
                HAVING SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) > 0 \
                ORDER BY total_shots DESC, total_goals DESC, player ASC;",
    "exp": "Aggregates the number of shots and goals for every player and computes a goal conversion percentage (goals as a percentage of shots). Only players with at least one shot or goal appear, sorted by shooting volume and goals.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show a table of all players with their shots, goals, and conversion rate.",
        "List every player along with how many shots and goals they had, plus their goal percentage.",
        "Provide a leaderboard of players by shots and goals, including goal conversion."
    ],
    "primary_key": "player"
    },
    {
    "id": 64,
    "question": "Show, for each team, how many times they recorded each event type (shots, goals, fouls, cards, offsides, corners, free kicks).",
    "query": "SELECT \
                team, \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END) AS shots, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS goals, \
                SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls, \
                SUM(CASE WHEN event_type IN ('yellow card','red card','sent off') THEN 1 ELSE 0 END) AS cards, \
                SUM(CASE WHEN event_type = 'offside' THEN 1 ELSE 0 END) AS offsides, \
                SUM(CASE WHEN event_type = 'corner kick' THEN 1 ELSE 0 END) AS corners, \
                SUM(CASE WHEN event_type = 'free kick' THEN 1 ELSE 0 END) AS free_kicks \
                FROM {table_name} \
                GROUP BY team \
                ORDER BY goals DESC, shots DESC, team ASC;",
    "exp": "Counts, for every team, how many of each key event type they produced. This builds a multi-row team profile table for the whole match.",
    "variables": ["table_name"],
    "paraphrases": [
        "Give me a per-team breakdown of all event types (shots, goals, fouls, cards, offsides, corners, free kicks).",
        "List every team with counts of their major events throughout the game.",
        "Show a team-level summary table of all key soccer events."
    ],
    "primary_key": "team"
    },
    {
    "id": 65,
    "question": "Show attacking intensity per team in every 10-minute window of the match (shots, corners, free kicks, goals).",
    "query": "SELECT \
                team, \
                ((minute - 1) / 10) AS window_index, \
                MIN(minute) AS window_start_minute, \
                MAX(minute) AS window_end_minute, \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END) AS shots, \
                SUM(CASE WHEN event_type = 'corner kick' THEN 1 ELSE 0 END) AS corners, \
                SUM(CASE WHEN event_type = 'free kick' THEN 1 ELSE 0 END) AS free_kicks, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS goals \
                FROM {table_name} \
                WHERE event_type IN ('shot','corner kick','free kick','goal') \
                GROUP BY team, ((minute - 1) / 10) \
                ORDER BY window_index ASC, team ASC;",
    "exp": "Divides the match into 10-minute windows using integer buckets and, for each team and window, counts key attacking events. Produces many rows: one per team per window where they attacked.",
    "variables": ["table_name"],
    "paraphrases": [
        "For every 10-minute slice, show how each team attacked (shots, corners, free kicks, goals).",
        "List attacking intensity per team across 10-minute intervals.",
        "Provide a table of team attacking events, broken down into 10-minute windows."
    ],
    "primary_key": ["team","window_index"]
    },
    {
    "id": 66,
    "question": "List all players with the fouls they committed and cards they received (yellow, red, sent off).",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls_committed, \
                SUM(CASE WHEN event_type = 'yellow card' THEN 1 ELSE 0 END) AS yellow_cards, \
                SUM(CASE WHEN event_type = 'red card' THEN 1 ELSE 0 END) AS red_cards, \
                SUM(CASE WHEN event_type = 'sent off' THEN 1 ELSE 0 END) AS sent_offs \
                FROM {table_name} \
                GROUP BY player, team \
                HAVING fouls_committed > 0 \
                    OR yellow_cards > 0 \
                    OR red_cards > 0 \
                    OR sent_offs > 0 \
                ORDER BY (yellow_cards + red_cards + sent_offs) DESC, fouls_committed DESC, player ASC;",
    "exp": "Aggregates discipline metrics for each player: fouls committed and all card types they received. Only players involved in at least one such event are shown.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show a discipline report per player: fouls and cards.",
        "List all players along with how many fouls and cards they got.",
        "Provide a player-by-player breakdown of fouls, yellow cards, reds, and send-offs."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 67,
    "question": "For each player, show the minute of their first involvement, last involvement, and the span of minutes they were active in the match.",
    "query": "SELECT \
                player, \
                team, \
                MIN(minute) AS first_minute, \
                MAX(minute) AS last_minute, \
                (MAX(minute) - MIN(minute)) AS active_span_minutes \
                FROM {table_name} \
                GROUP BY player, team \
                ORDER BY first_minute ASC, player ASC;",
    "exp": "For each player, finds their earliest and latest event in the match log and computes the span between them. This gives a rough active interval per player.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show when each player first appeared in the event log, when they last appeared, and the duration in between.",
        "List all players with the span of time they were active in the match events.",
        "Provide a table of players showing first minute, last minute, and total active duration."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 68,
    "question": "For each team, show how many shots and goals they took where the description mentions being in or near the box.",
    "query": "SELECT \
                team, \
                SUM(CASE WHEN event_type = 'shot' \
                            AND (LOWER(description) LIKE '%box%' \
                            OR LOWER(description) LIKE '%penalty area%' \
                            OR LOWER(description) LIKE '%penalty box%') \
                        THEN 1 ELSE 0 END) AS box_shots, \
                SUM(CASE WHEN event_type = 'goal' \
                            AND (LOWER(description) LIKE '%box%' \
                            OR LOWER(description) LIKE '%penalty area%' \
                            OR LOWER(description) LIKE '%penalty box%') \
                        THEN 1 ELSE 0 END) AS box_goals \
                FROM {table_name} \
                GROUP BY team \
                ORDER BY box_shots DESC, box_goals DESC, team ASC;",
    "exp": "Counts, for every team, how many of their shots and goals are explicitly described as occurring in/near the box. Produces a multi-row table of box-related attacking stats.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show per-team stats for shots and goals taken from in or around the box.",
        "List all teams with how many box-related shots and goals they had.",
        "Provide a team-wise table of shots/goals described as 'in the box'."
    ],
    "primary_key": "team"
    },
    {
    "id": 69,
    "question": "List all players and how many set-piece events (free kicks and corner kicks) they took, along with any goals from those events.",
    "query": "WITH set_pieces AS ( \
                SELECT minute, team, player, event_type \
                FROM {table_name} \
                WHERE event_type IN ('free kick','corner kick') \
                ), \
                goals AS ( \
                SELECT minute, team, player \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                ) \
                SELECT \
                s.player, \
                s.team, \
                SUM(CASE WHEN s.event_type = 'free kick' THEN 1 ELSE 0 END) AS free_kicks_taken, \
                SUM(CASE WHEN s.event_type = 'corner kick' THEN 1 ELSE 0 END) AS corners_taken, \
                SUM(CASE WHEN g.minute IS NOT NULL THEN 1 ELSE 0 END) AS goals_in_same_minute \
                FROM set_pieces s \
                LEFT JOIN goals g \
                ON g.team = s.team \
                AND g.minute = s.minute \
                GROUP BY s.player, s.team \
                ORDER BY (free_kicks_taken + corners_taken) DESC, s.player ASC;",
    "exp": "Builds a table of set-piece takers by player, counting how many free kicks and corners they took and whether any goals were recorded in the same minute for their team.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show which players took the most free kicks and corners, and how many of those led to goals in the same minute.",
        "List all set-piece takers with their free kick and corner counts.",
        "Provide a table of players heavily involved in set-piece situations."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 70,
    "question": "Show, for every team and 5-minute window, the total attacking events as a simple momentum proxy.",
    "query": "SELECT \
                team, \
                ((minute - 1) / 5) AS window_index, \
                MIN(minute) AS window_start_minute, \
                MAX(minute) AS window_end_minute, \
                COUNT(*) AS attacking_events \
                FROM {table_name} \
                WHERE event_type IN ('shot','corner kick','free kick','goal') \
                GROUP BY team, ((minute - 1) / 5) \
                ORDER BY window_index ASC, attacking_events DESC, team ASC;",
    "exp": "Treats all attacking events (shots, corners, free kicks, goals) as momentum indicators, counts them per team in 5-minute windows, and returns a table of momentum values over time.",
    "variables": ["table_name"],
    "paraphrases": [
        "Provide a momentum table where each row is a team and 5-minute window with the number of attacking events.",
        "Show how each team's attacking momentum evolved every 5 minutes.",
        "List attacking-event counts per team per 5-minute period."
    ],
    "primary_key": ["team","window_index"]
    },
    {
    "id": 71,
    "question": "For each team, show their fouls committed, fouls suffered (inferred from opponent fouls), and cards received.",
    "query": "WITH fouls AS ( \
                SELECT minute, team, player \
                FROM {table_name} \
                WHERE event_type = 'foul' \
                ), \
                teams AS ( \
                SELECT DISTINCT team FROM {table_name} \
                ) \
                SELECT \
                t.team, \
                -- fouls this team committed \
                COALESCE( \
                    (SELECT COUNT(*) FROM fouls f1 WHERE f1.team = t.team), 0 \
                ) AS fouls_committed, \
                -- fouls this team suffered (fouls recorded for opponents) \
                COALESCE( \
                    (SELECT COUNT(*) FROM fouls f2 WHERE f2.team <> t.team), 0 \
                ) AS fouls_suffered_proxy, \
                -- cards received by this team \
                COALESCE( \
                    (SELECT COUNT(*) \
                    FROM {table_name} c \
                    WHERE c.team = t.team \
                    AND c.event_type IN ('yellow card','red card','sent off')), \
                    0 \
                ) AS cards_received \
                FROM teams t \
                ORDER BY fouls_committed DESC, cards_received DESC, t.team ASC;",
    "exp": "Builds a team-wise table with fouls they committed, an approximate count of fouls they suffered (opponent fouls), and how many cards they received, producing a broad discipline-versus-pressure profile.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show a table of each team's fouls committed, fouls against them, and cards they received.",
        "List discipline and pressure metrics per team (fouls and cards).",
        "Provide a balance overview: fouls made, fouls suffered, and cards per team."
    ],
    "primary_key": "team"
    },
    {
    "id": 72,
    "question": "List all shots taken in the match with minute, team, player, and a flag whether the shot was a goal.",
    "query": "SELECT \
                minute, \
                team, \
                player, \
                CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END AS is_goal \
                FROM {table_name} \
                WHERE event_type IN ('shot','goal') \
                ORDER BY minute ASC, team ASC, player ASC;",
    "exp": "Returns one row per shot-like event in the match with explicit indication of whether it was a goal. This gives a dense table of all shooting actions over time.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show a timeline of every shot in the match, with who took it and if it was a goal.",
        "List all shot and goal events in order with flags marking goals.",
        "Provide a minute-by-minute shot map including the scoring shots."
    ],
    "primary_key": ["minute","team","player"]
    },
    {
    "id": 73,
    "question": "Which team completed the most multi-hop set-piece attack chains defined as: an opponent foul, followed within 2 minutes by this team taking a free kick or corner kick, followed within 2 more minutes by this team taking a shot or scoring a goal?",
    "query": "WITH fouls AS ( \
                SELECT minute AS foul_minute, team AS fouling_team \
                FROM {table_name} \
                WHERE event_type = 'foul' \
                ), \
                set_pieces AS ( \
                SELECT minute AS sp_minute, team, event_type \
                FROM {table_name} \
                WHERE event_type IN ('free kick','corner kick') \
                ), \
                shots AS ( \
                SELECT minute AS shot_minute, team \
                FROM {table_name} \
                WHERE event_type IN ('shot','goal') \
                ), \
                foul_to_sp AS ( \
                SELECT \
                    sp.team AS attacking_team, \
                    f.foul_minute, \
                    sp.sp_minute \
                FROM fouls f \
                JOIN set_pieces sp \
                    ON sp.team <> f.fouling_team \
                AND sp.sp_minute > f.foul_minute \
                AND sp.sp_minute <= f.foul_minute + 2 \
                ), \
                full_chain AS ( \
                SELECT \
                    fs.attacking_team, \
                    fs.foul_minute, \
                    fs.sp_minute, \
                    sh.shot_minute \
                FROM foul_to_sp fs \
                JOIN shots sh \
                    ON sh.team = fs.attacking_team \
                AND sh.shot_minute > fs.sp_minute \
                AND sh.shot_minute <= fs.sp_minute + 2 \
                ) \
                SELECT \
                attacking_team AS team, \
                COUNT(*) AS completed_chains, \
                COUNT(DISTINCT foul_minute) AS distinct_starting_fouls \
                FROM full_chain \
                GROUP BY attacking_team \
                ORDER BY completed_chains DESC, team ASC;",
    "exp": "Treat every foul as a potential possession regain for the non-fouling side. For each foul, look for a free kick or corner by the other team within 2 minutes, then a shot or goal by the same team within 2 further minutes. Count all such chains per team.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team most often turned opponent fouls into a set-piece followed by a shot or goal?",
        "List teams by how many foul → (free kick / corner) → shot/goal chains they produced.",
        "Who built the most multi-hop set-piece attacks starting from opponent fouls?"
    ],
    "primary_key": "team"
    },
    {
    "id": 74,
    "question": "Which players both scored at least one goal and later were booked or sent off (yellow card, red card, or sent off), and how many minutes elapsed between their first goal and their first card/send-off?",
    "query": "WITH goals AS ( \
                SELECT player, team, MIN(minute) AS first_goal_minute \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                GROUP BY player, team \
                ), \
                cards AS ( \
                SELECT player, team, MIN(minute) AS first_card_minute \
                FROM {table_name} \
                WHERE event_type IN ('yellow card','red card','sent off') \
                GROUP BY player, team \
                ), \
                joined AS ( \
                SELECT \
                    g.player, \
                    g.team, \
                    g.first_goal_minute, \
                    c.first_card_minute \
                FROM goals g \
                JOIN cards c \
                    ON c.player = g.player \
                AND c.team = g.team \
                AND c.first_card_minute > g.first_goal_minute \
                ) \
                SELECT \
                player, \
                team, \
                first_goal_minute, \
                first_card_minute, \
                (first_card_minute - first_goal_minute) AS minutes_between_goal_and_card \
                FROM joined \
                ORDER BY minutes_between_goal_and_card ASC, player ASC, team ASC;",
    "exp": "Finds players who scored at least one goal and, after that, received a yellow/red card or were sent off. For each such player, it uses the first goal minute and the first later card/send-off minute to compute how many minutes separated those events.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which goal scorers later got booked or sent off, and how long after scoring did that happen?",
        "List players who both scored and then received a card, with the time gap between the goal and the card.",
        "Show all players whose match storyline was: goal first, then later card/send-off, including the minute difference."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 75,
    "question": "Which players both committed at least one foul and scored at least one goal, and what were their counts of fouls and goals?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls_committed, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS goals_scored \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) > 0 \
                AND SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) > 0 \
            ORDER BY goals_scored DESC, fouls_committed DESC, player ASC;",
    "exp": "Aggregates, per player and team, how many fouls they committed and how many goals they scored. Filters to players who did both at least once, and orders by goals and then fouls.",
    "variables": ["table_name"],
    "paraphrases": [
        "List all players who both fouled and scored, with their foul and goal counts.",
        "Which players committed at least one foul and also scored at least one goal?",
        "Show players who appear as both foulers and goal scorers, and how many fouls and goals they had."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 76,
    "question": "Which players committed fouls, received a card (yellow, red, or sent off), and scored at least one goal in the match?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls_committed, \
                SUM(CASE WHEN event_type IN ('yellow card','red card','sent off') THEN 1 ELSE 0 END) AS cards_received, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS goals_scored \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) > 0 \
                AND SUM(CASE WHEN event_type IN ('yellow card','red card','sent off') THEN 1 ELSE 0 END) > 0 \
                AND SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) > 0 \
            ORDER BY goals_scored DESC, cards_received DESC, fouls_committed DESC, player ASC;",
    "exp": "Finds players who tick all three boxes: they committed at least one foul, received at least one card (yellow, red, or sent off), and scored at least one goal. Shows their counts for each category.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players fouled, were carded, and also scored in the same match?",
        "List players who committed fouls, received a card, and scored at least one goal, with all three counts.",
        "Show multi-role players who feature as foulers, card recipients, and goal scorers."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 77,
    "question": "Which players took at least one shot, at least one free kick, and at least one corner kick, and how many of each did they take?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END) AS shots_taken, \
                SUM(CASE WHEN event_type = 'free kick' THEN 1 ELSE 0 END) AS free_kicks_taken, \
                SUM(CASE WHEN event_type = 'corner kick' THEN 1 ELSE 0 END) AS corners_taken \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END) > 0 \
                AND SUM(CASE WHEN event_type = 'free kick' THEN 1 ELSE 0 END) > 0 \
                AND SUM(CASE WHEN event_type = 'corner kick' THEN 1 ELSE 0 END) > 0 \
            ORDER BY (shots_taken + free_kicks_taken + corners_taken) DESC, player ASC;",
    "exp": "Identifies players who contributed in three different attacking roles: general shooting, taking free kicks, and taking corner kicks. Counts each type of action per player and returns only those who did all three.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players were involved as shooters, free-kick takers, and corner takers?",
        "List players who recorded at least one shot, one free kick, and one corner kick.",
        "Show multi-role attackers with counts of shots, free kicks, and corners each player took."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 78,
    "question": "Which players both delivered crosses and took shots/goals themselves, and how many crossing and finishing actions did they have?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN LOWER(description) LIKE '%cross%' OR LOWER(description) LIKE '%delivery%' THEN 1 ELSE 0 END) AS crossing_actions, \
                SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS finishing_actions \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                SUM(CASE WHEN LOWER(description) LIKE '%cross%' OR LOWER(description) LIKE '%delivery%' THEN 1 ELSE 0 END) > 0 \
                AND SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) > 0 \
            ORDER BY finishing_actions DESC, crossing_actions DESC, player ASC;",
    "exp": "Uses the description field to detect crossing or delivery actions and combines that with shot/goal events. Returns players who were involved both as crossers/creators and as finishers.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players both put in crosses/deliveries and also took shots or scored?",
        "List players who contributed as both providers (crosses) and shooters/goal scorers.",
        "Show players with counts of crossing-type actions and finishing actions."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 79,
    "question": "Which players took both 'header' shots and non-header shots, and how many of each did they attempt?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type IN ('shot','goal') AND LOWER(description) LIKE '%header%' THEN 1 ELSE 0 END) AS header_shots, \
                SUM(CASE WHEN event_type IN ('shot','goal') AND LOWER(description) NOT LIKE '%header%' THEN 1 ELSE 0 END) AS non_header_shots \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                SUM(CASE WHEN event_type IN ('shot','goal') AND LOWER(description) LIKE '%header%' THEN 1 ELSE 0 END) > 0 \
                AND SUM(CASE WHEN event_type IN ('shot','goal') AND LOWER(description) NOT LIKE '%header%' THEN 1 ELSE 0 END) > 0 \
            ORDER BY (header_shots + non_header_shots) DESC, player ASC;",
    "exp": "Separates a player's shooting actions into headers (based on 'header' in the description) and non-headers. Returns only those players who attempted at least one of each, along with their respective counts.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players attempted both header shots and non-header shots?",
        "List players with counts of header-based attempts and other shooting attempts.",
        "Show players who mixed heading attempts with other types of shots."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 80,
    "question": "Which players attempted both long-range shots and box shots, and how many did they take of each type?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type IN ('shot','goal') \
                        AND (LOWER(description) LIKE '%outside the box%' OR LOWER(description) LIKE '%long range%') \
                        THEN 1 ELSE 0 END) AS long_range_attempts, \
                SUM(CASE WHEN event_type IN ('shot','goal') \
                        AND (LOWER(description) LIKE '%inside the box%' OR LOWER(description) LIKE '%in the box%' OR LOWER(description) LIKE '%penalty box%') \
                        THEN 1 ELSE 0 END) AS box_attempts \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                long_range_attempts > 0 \
                AND box_attempts > 0 \
            ORDER BY (long_range_attempts + box_attempts) DESC, player ASC;",
    "exp": "Classifies each player's shooting actions into long-range attempts (descriptions like 'outside the box' or 'long range') and box attempts (descriptions mentioning the box). Returns players who have at least one of each type, with counts.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players have both long-range attempts and shots from inside the box?",
        "List players who shot from distance and also from in or around the box, with counts of each.",
        "Show a table of players who mixed long-range and box-area shooting."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 81,
    "question": "Which players contributed in both attacking and defensive ways by having at least one shot and at least one foul committed?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS attacking_actions, \
                SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls_committed \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) > 0 \
                AND SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) > 0 \
            ORDER BY attacking_actions DESC, fouls_committed DESC, player ASC;",
    "exp": "Counts attacking actions (shots and goals) and fouls committed per player. Filters to those who did at least one of each, indicating players with both attacking and defensive/physical involvement.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players both took shots/goals and committed fouls in the same match?",
        "List players with at least one attacking action and at least one foul committed.",
        "Show players who were active both in attack (shots/goals) and in committing fouls."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 82,
    "question": "Which players both took set pieces (free kicks or corner kicks) and scored at least one goal, and how many set pieces did they take?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type IN ('free kick','corner kick') THEN 1 ELSE 0 END) AS set_pieces_taken, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) AS goals_scored \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                set_pieces_taken > 0 \
                AND goals_scored > 0 \
            ORDER BY goals_scored DESC, set_pieces_taken DESC, player ASC;",
    "exp": "Looks for players who were both set-piece takers (free kicks or corners) and also scored at least one goal. Shows how many set pieces they took and how many goals they scored.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players both took free kicks or corners and also scored?",
        "List players who combined set-piece taking duties with scoring at least one goal.",
        "Show players with counts of set pieces taken and goals scored."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 83,
    "question": "Which players received at least one card (yellow, red, or sent off) and also took at least one shot or scored a goal?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type IN ('yellow card','red card','sent off') THEN 1 ELSE 0 END) AS cards_received, \
                SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS attacking_actions \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                cards_received > 0 \
                AND attacking_actions > 0 \
            ORDER BY cards_received DESC, attacking_actions DESC, player ASC;",
    "exp": "Combines discipline and attacking involvement by finding players who both received at least one card and also took at least one shot or scored. Returns their card count and attacking-event count.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which booked players (yellow/red/sent off) also took shots or scored?",
        "List players who both received a card and were involved in shooting or scoring.",
        "Show players with at least one card and at least one attacking action."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 84,
    "question": "Which players showed diverse attacking contribution by both attempting a shot and having at least one event described as a 'cross' or 'delivery'?",
    "query": "SELECT \
                player, \
                team, \
                SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS shots_and_goals, \
                SUM(CASE WHEN LOWER(description) LIKE '%cross%' OR LOWER(description) LIKE '%delivery%' THEN 1 ELSE 0 END) AS crossing_or_delivery_events \
            FROM {table_name} \
            GROUP BY player, team \
            HAVING \
                shots_and_goals > 0 \
                AND crossing_or_delivery_events > 0 \
            ORDER BY (shots_and_goals + crossing_or_delivery_events) DESC, player ASC;",
    "exp": "Counts, for each player, how many shooting events (shots/goals) they had and how many of their events are described as crosses or deliveries. Returns only players who contributed in both finishing and creating roles.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players both took shots/goals and also played in crosses or deliveries?",
        "List players who appeared as both finishers and cross/delivery providers.",
        "Show players with at least one shot/goal and at least one cross/delivery-type event."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 85,
    "question": "Which players took at least 40% of their team's total shots (including goals as shots), and what were their individual and team shot counts?",
    "query": "WITH team_shots AS ( \
                SELECT team, COUNT(*) AS team_shots \
                FROM {table_name} \
                WHERE event_type IN ('shot','goal') \
                GROUP BY team \
                ), \
                player_shots AS ( \
                SELECT player, team, COUNT(*) AS player_shots \
                FROM {table_name} \
                WHERE event_type IN ('shot','goal') \
                GROUP BY player, team \
                ) \
                SELECT \
                ps.player, \
                ps.team, \
                ps.player_shots, \
                ts.team_shots, \
                ROUND(ps.player_shots * 100.0 / NULLIF(ts.team_shots, 0), 2) AS shot_share_percentage \
                FROM player_shots ps \
                JOIN team_shots ts \
                ON ts.team = ps.team \
                WHERE ps.player_shots * 1.0 >= 0.40 * ts.team_shots \
                ORDER BY shot_share_percentage DESC, ps.player ASC;",
    "exp": "First initializes team-level total shots (including goals) and player-level shots per team. Then filters to players whose shots represent at least 40% of their team's total and reports their share.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players took at least 40% of their team's shots/goals?",
        "List players whose shot volume was 40% or more of their team's total attempts.",
        "Show high-usage shooters with their shot counts and share of team shots."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 86,
    "question": "Compared to {player}, which players had more total attacking actions (shots and goals), and by how much?",
    "query": "WITH per_player AS ( \
                SELECT \
                    player, \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS attacking_actions \
                FROM {table_name} \
                GROUP BY player, team \
                ), \
                ref AS ( \
                SELECT attacking_actions AS ref_attacking_actions \
                FROM per_player \
                WHERE player = '{player}' \
                ORDER BY attacking_actions DESC \
                LIMIT 1 \
                ) \
                SELECT \
                p.player, \
                p.team, \
                p.attacking_actions, \
                r.ref_attacking_actions, \
                (p.attacking_actions - r.ref_attacking_actions) AS attacking_diff \
                FROM per_player p \
                CROSS JOIN ref r \
                WHERE p.attacking_actions > r.ref_attacking_actions \
                ORDER BY attacking_diff DESC, p.attacking_actions DESC, p.player ASC;",
    "exp": "First aggregates per-player attacking actions (shots and goals). Then isolates {player}'s attacking total in a reference CTE. Finally returns all players whose attacking_actions exceed that reference, along with the difference.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Which players took more shots/goals than {player}, and by how many?",
        "List all players whose attacking actions exceeded those of {player}.",
        "Show the difference in attacking involvement between {player} and all players who did better."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 87,
    "question": "Compared to {player}, which players committed more fouls or received more cards (yellow, red, sent off), and what are the differences?",
    "query": "WITH per_player AS ( \
                SELECT \
                    player, \
                    team, \
                    SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls_committed, \
                    SUM(CASE WHEN event_type IN ('yellow card','red card','sent off') THEN 1 ELSE 0 END) AS cards_received \
                FROM {table_name} \
                GROUP BY player, team \
                ), \
                ref AS ( \
                SELECT \
                    fouls_committed AS ref_fouls, \
                    cards_received AS ref_cards \
                FROM per_player \
                WHERE player = '{player}' \
                ORDER BY fouls_committed DESC, cards_received DESC \
                LIMIT 1 \
                ) \
                SELECT \
                p.player, \
                p.team, \
                p.fouls_committed, \
                p.cards_received, \
                r.ref_fouls, \
                r.ref_cards, \
                (p.fouls_committed - r.ref_fouls) AS foul_diff, \
                (p.cards_received - r.ref_cards) AS card_diff \
                FROM per_player p \
                CROSS JOIN ref r \
                WHERE p.fouls_committed > r.ref_fouls \
                OR p.cards_received > r.ref_cards \
                ORDER BY (p.fouls_committed + p.cards_received) DESC, p.player ASC;",
    "exp": "Aggregates fouls and card counts per player, stores {player}'s numbers in a reference CTE, then returns all players who either committed more fouls or received more cards than {player}, along with differences for each metric.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Which players had more fouls or more cards than {player}?",
        "Show all players who were more ill-disciplined than {player}, with foul and card differences.",
        "Compare {player}'s fouls and cards to others and list who exceeded them."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 88,
    "question": "Compared to {player}, which players were more versatile in terms of distinct event types they appeared in?",
    "query": "WITH per_player AS ( \
                SELECT \
                    player, \
                    team, \
                    COUNT(DISTINCT event_type) AS distinct_event_types \
                FROM {table_name} \
                GROUP BY player, team \
                ), \
                ref AS ( \
                SELECT distinct_event_types AS ref_types \
                FROM per_player \
                WHERE player = '{player}' \
                ORDER BY distinct_event_types DESC \
                LIMIT 1 \
                ) \
                SELECT \
                p.player, \
                p.team, \
                p.distinct_event_types, \
                r.ref_types AS ref_distinct_event_types, \
                (p.distinct_event_types - r.ref_types) AS type_diff \
                FROM per_player p \
                CROSS JOIN ref r \
                WHERE p.distinct_event_types > r.ref_types \
                ORDER BY type_diff DESC, p.distinct_event_types DESC, p.player ASC;",
    "exp": "Counts how many distinct event types each player is involved in, uses {player}'s count as a reference, then returns players who are involved in more event types than {player}.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Which players had a wider variety of event types than {player}?",
        "List players who were involved in more different types of events than {player}.",
        "Show who was more versatile than {player} in terms of event-role diversity."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 89,
    "question": "Which players have a higher share of their team's shots than {player} has of their own team's shots, and what are those shares?",
    "query": "WITH player_team_shots AS ( \
                SELECT \
                    player, \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS player_shots \
                FROM {table_name} \
                GROUP BY player, team \
                ), \
                team_shots AS ( \
                SELECT \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS team_shots \
                FROM {table_name} \
                GROUP BY team \
                ), \
                per_player AS ( \
                SELECT \
                    p.player, \
                    p.team, \
                    p.player_shots, \
                    t.team_shots, \
                    CASE WHEN t.team_shots > 0 \
                        THEN p.player_shots * 100.0 / t.team_shots \
                        ELSE 0 END AS shot_share_pct \
                FROM player_team_shots p \
                JOIN team_shots t ON t.team = p.team \
                ), \
                ref AS ( \
                SELECT shot_share_pct AS ref_share \
                FROM per_player \
                WHERE player = '{player}' \
                ORDER BY shot_share_pct DESC \
                LIMIT 1 \
                ) \
                SELECT \
                p.player, \
                p.team, \
                p.player_shots, \
                p.team_shots, \
                ROUND(p.shot_share_pct, 2) AS shot_share_pct, \
                ROUND(r.ref_share, 2) AS ref_shot_share_pct, \
                ROUND(p.shot_share_pct - r.ref_share, 2) AS share_diff_pct \
                FROM per_player p \
                CROSS JOIN ref r \
                WHERE p.shot_share_pct > r.ref_share \
                ORDER BY share_diff_pct DESC, p.shot_share_pct DESC, p.player ASC;",
    "exp": "Computes, for each player, what percentage of their team's shots/goals they took. Then uses {player}'s shot share as a reference and lists all players whose team shot share is higher than that of {player}.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Which players were even more shot-dominant for their team than {player} was for theirs?",
        "List players whose share of team shots exceeds {player}'s shot share.",
        "Compare team-shot reliance on {player} with other players and show who had higher shares."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 90,
    "question": "Compared to {player}, which players had a higher attacking-to-foul ratio (shots and goals divided by fouls committed)?",
    "query": "WITH per_player AS ( \
                SELECT \
                    player, \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS attacking_actions, \
                    SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls_committed \
                FROM {table_name} \
                GROUP BY player, team \
                ), \
                with_ratio AS ( \
                SELECT \
                    player, \
                    team, \
                    attacking_actions, \
                    fouls_committed, \
                    CASE WHEN fouls_committed > 0 \
                        THEN attacking_actions * 1.0 / fouls_committed \
                        ELSE NULL END AS attack_foul_ratio \
                FROM per_player \
                ), \
                ref AS ( \
                SELECT attack_foul_ratio AS ref_ratio \
                FROM with_ratio \
                WHERE player = '{player}' \
                ORDER BY attack_foul_ratio DESC NULLS LAST \
                LIMIT 1 \
                ) \
                SELECT \
                w.player, \
                w.team, \
                w.attacking_actions, \
                w.fouls_committed, \
                ROUND(w.attack_foul_ratio, 2) AS attack_foul_ratio, \
                ROUND(r.ref_ratio, 2) AS ref_attack_foul_ratio, \
                ROUND(w.attack_foul_ratio - r.ref_ratio, 2) AS ratio_diff \
                FROM with_ratio w \
                CROSS JOIN ref r \
                WHERE w.attack_foul_ratio IS NOT NULL \
                AND r.ref_ratio IS NOT NULL \
                AND w.attack_foul_ratio > r.ref_ratio \
                ORDER BY ratio_diff DESC, w.attack_foul_ratio DESC, w.player ASC;",
    "exp": "Builds per-player counts of attacking actions and fouls, computes an attacking-to-fouls ratio, and then compares all players against {player}'s ratio, returning those with a higher ratio.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Which players had a better ratio of attacking actions to fouls than {player}?",
        "List players whose shots+goals per foul committed exceed {player}'s ratio.",
        "Compare {player}'s attack-versus-foul profile with others and show who is more 'efficient'."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 91,
    "question": "Which players had more box-related attacking actions (shots/goals described as in or near the box) than {player} did?",
    "query": "WITH per_player AS ( \
                SELECT \
                    player, \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') \
                            AND (LOWER(description) LIKE '%inside the box%' \
                                OR LOWER(description) LIKE '%in the box%' \
                                OR LOWER(description) LIKE '%penalty box%' \
                                OR LOWER(description) LIKE '%six-yard box%') \
                            THEN 1 ELSE 0 END) AS box_attacks \
                FROM {table_name} \
                GROUP BY player, team \
                ), \
                ref AS ( \
                SELECT box_attacks AS ref_box_attacks \
                FROM per_player \
                WHERE player = '{player}' \
                ORDER BY box_attacks DESC \
                LIMIT 1 \
                ) \
                SELECT \
                p.player, \
                p.team, \
                p.box_attacks, \
                r.ref_box_attacks, \
                (p.box_attacks - r.ref_box_attacks) AS box_attack_diff \
                FROM per_player p \
                CROSS JOIN ref r \
                WHERE p.box_attacks > r.ref_box_attacks \
                ORDER BY box_attack_diff DESC, p.box_attacks DESC, p.player ASC;",
    "exp": "Counts, for each player, how many shots/goals are described as inside or near the box. Then compares all players to {player} and returns those with more such box-related actions.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Who had more box-area shots/goals than {player}?",
        "List players with a higher count of box-related attacking actions compared to {player}.",
        "Show players whose in-box involvement exceeds that of {player}."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 92,
    "question": "Which players had more set-piece actions (free kicks and corner kicks taken) than {player}?",
    "query": "WITH per_player AS ( \
                SELECT \
                    player, \
                    team, \
                    SUM(CASE WHEN event_type IN ('free kick','corner kick') THEN 1 ELSE 0 END) AS set_pieces_taken \
                FROM {table_name} \
                GROUP BY player, team \
                ), \
                ref AS ( \
                SELECT set_pieces_taken AS ref_set_pieces \
                FROM per_player \
                WHERE player = '{player}' \
                ORDER BY set_pieces_taken DESC \
                LIMIT 1 \
                ) \
                SELECT \
                p.player, \
                p.team, \
                p.set_pieces_taken, \
                r.ref_set_pieces, \
                (p.set_pieces_taken - r.ref_set_pieces) AS set_piece_diff \
                FROM per_player p \
                CROSS JOIN ref r \
                WHERE p.set_pieces_taken > r.ref_set_pieces \
                ORDER BY set_piece_diff DESC, p.set_pieces_taken DESC, p.player ASC;",
    "exp": "Aggregates free kicks and corners taken by each player, retrieves {player}'s count as a reference, and returns all players who took more set pieces than {player}.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Which players took more free kicks and corners than {player}?",
        "List players whose set-piece volume was higher than {player}'s.",
        "Show all players who were bigger set-piece takers than {player}."
    ],
    "primary_key": ["player","team"]
    },
    {
    "id": 93,
    "question": "Which players had a higher overall involvement index (shots/goals + fouls + cards) than {player}, and what is their index difference?",
    "query": "WITH per_player AS ( \
                SELECT \
                    player, \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','goal') THEN 1 ELSE 0 END) AS attacking_actions, \
                    SUM(CASE WHEN event_type = 'foul' THEN 1 ELSE 0 END) AS fouls_committed, \
                    SUM(CASE WHEN event_type IN ('yellow card','red card','sent off') THEN 1 ELSE 0 END) AS cards_received \
                FROM {table_name} \
                GROUP BY player, team \
                ), \
                with_index AS ( \
                SELECT \
                    player, \
                    team, \
                    attacking_actions, \
                    fouls_committed, \
                    cards_received, \
                    (attacking_actions + fouls_committed + cards_received) AS involvement_index \
                FROM per_player \
                ), \
                ref AS ( \
                SELECT involvement_index AS ref_index \
                FROM with_index \
                WHERE player = '{player}' \
                ORDER BY involvement_index DESC \
                LIMIT 1 \
                ) \
                SELECT \
                w.player, \
                w.team, \
                w.attacking_actions, \
                w.fouls_committed, \
                w.cards_received, \
                w.involvement_index, \
                r.ref_index AS ref_involvement_index, \
                (w.involvement_index - r.ref_index) AS index_diff \
                FROM with_index w \
                CROSS JOIN ref r \
                WHERE w.involvement_index > r.ref_index \
                ORDER BY index_diff DESC, w.involvement_index DESC, w.player ASC;",
    "exp": "Builds an overall involvement index per player (sum of shots/goals, fouls, and cards), then compares everyone to {player}'s index and lists those who were more involved according to this composite measure.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Who had a higher overall involvement (attacking, fouls, and cards) than {player}?",
        "List players whose combined index of shots/goals, fouls, and cards exceeded {player}'s.",
        "Show players more involved in the match events than {player}, with index differences."
    ],
    "primary_key": ["player","team"]
    }
]