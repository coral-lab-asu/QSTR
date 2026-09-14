question_football = [
    {
    "id": 1,
    "question": "Which player scored the most goals and how many goals did they score?",
    "query": "SELECT player, COUNT(*) AS total_goals \
            FROM {table_name} \
            WHERE event_type = 'goal' \
            GROUP BY player \
            HAVING COUNT(*) = ( \
                SELECT MAX(goal_count) \
                FROM ( \
                    SELECT COUNT(*) AS goal_count \
                    FROM {table_name} \
                    WHERE event_type = 'goal' \
                    GROUP BY player \
                ) AS sub \
            );",
    "exp": "Filter rows where event_type = 'goal', group them by player, count goals, and return the player(s) with the highest goal count.",
    "variables": ["table_name"],
    "paraphrases": [
    "Who was the top goal scorer in the match, and how many goals did they get?",
    "Which player found the net the most times, and what is their goal tally?",
    "Identify the player with the highest goal count and return the exact number."
    ]
    },
    {
    "id": 2,
    "question": "Which player attempted the most crosses and how many crosses did they attempt?",
    "query": "SELECT player, COUNT(*) AS total_crosses \
            FROM {table_name} \
            WHERE event_type = 'cross' \
            GROUP BY player \
            HAVING COUNT(*) = ( \
                SELECT MAX(cross_count) \
                FROM ( \
                SELECT COUNT(*) AS cross_count \
                FROM {table_name} \
                WHERE event_type = 'cross' \
                GROUP BY player \
                ) AS x \
            );",
    "exp": "Group all rows with event_type = cross by player, count them, and return the player with the highest count.",
    "variables": ["table_name"],
    "paraphrases": [
    "Who delivered the most crosses, and how many did they make?",
    "Identify the player with the highest number of crosses attempted.",
    "Which player attempted the most crossing balls, and what was the count?"
    ]
    },
    {
    "id": 3,
    "question": "At what minute did {team} score their first goal, and who scored it?",
    "query": "SELECT minute, player \
            FROM {table_name} \
            WHERE team = '{team}' AND event_type = 'goal' \
            ORDER BY minute ASC \
            LIMIT 1;",
    "exp": "Filter goals by team, sort by minute, return earliest scoring event and the scorer.",
    "variables": ["table_name", "team"],
    "paraphrases": [
    "When did {team} score their opening goal and which player scored it?",
    "What was the first goal minute for {team} and who was the scorer?",
    "Find {team}'s earliest goal in the match and name the player responsible."
    ]
    },
    {
    "id": 4,
    "question": "How many corners did {team} take?",
    "query": "SELECT COUNT(*) AS total_corners \
            FROM {table_name} \
            WHERE team = '{team}' AND event_type = 'corner';",
    "exp": "Count all events where the event_type is corner for the given team.",
    "variables": ["table_name", "team"],
    "paraphrases": [
    "How many corner kicks were taken by {team}?",
    "Give the total number of corners awarded to {team}.",
    "Count the corners {team} had in the match."
    ]
    },
    {
    "id": 5,
    "question": "Which team received the most yellow cards and how many?",
    "query": "SELECT team, COUNT(*) AS total_yellows \
            FROM {table_name} \
            WHERE event_type = 'yellow_card' \
            GROUP BY team \
            HAVING COUNT(*) = ( \
                SELECT MAX(y_count) \
                FROM ( \
                SELECT COUNT(*) AS y_count \
                FROM {table_name} \
                WHERE event_type = 'yellow_card' \
                GROUP BY team \
                ) AS y \
            );",
    "exp": "Filter rows with yellow cards, group them by team, count them, and return the team with the most yellow cards.",
    "variables": ["table_name"],
    "paraphrases": [
    "Which team picked up the highest number of yellow cards?",
    "Who had the most bookings in the match?",
    "Identify the team receiving the most yellow cards and return the count."
    ]
    },
    {
    "id": 6,
    "question": "How many shots were taken by {player}?",
    "query": "SELECT COUNT(*) AS total_shots \
            FROM {table_name} \
            WHERE player = '{player}' AND event_type = 'shot';",
    "exp": "Count the number of shot events attributed to the specified player.",
    "variables": ["table_name", "player"],
    "paraphrases": [
    "How many shots did {player} attempt?",
    "What is the total number of shot attempts by {player}?",
    "Count the shots registered by {player} in the match."
    ]
    },
    {
    "id": 7,
    "question": "Which player was involved in the most total events and how many?",
    "query": "SELECT player, COUNT(*) AS event_count \
            FROM {table_name} \
            WHERE player IS NOT NULL AND player <> '' \
            GROUP BY player \
            HAVING COUNT(*) = ( \
                SELECT MAX(events) \
                FROM ( \
                SELECT COUNT(*) AS events \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                GROUP BY player \
                ) AS sub \
            );",
    "exp": "Group all events by player and return the one with the highest number of total events.",
    "variables": ["table_name"],
    "paraphrases": [
    "Which player appeared in the most events across the match?",
    "Who was the most active player based on event involvement?",
    "Find the player with the highest total number of event involvements."
    ]
    },
    {
    "id": 8,
    "question": "How many substitutions did {team} make?",
    "query": "SELECT COUNT(*) AS total_substitutions \
            FROM {table_name} \
            WHERE team = '{team}' AND event_type = 'substitution';",
    "exp": "Count substitution events for the specific team.",
    "variables": ["table_name", "team"],
    "paraphrases": [
    "How many substitutes did {team} bring on?",
    "Count the number of substitutions made by {team}.",
    "What is the total substitution count for {team}?"
    ]
    },
    {
    "id": 9,
    "question": "How many goals were scored between minute {m1} and {m2}?",
    "query": "SELECT COUNT(*) AS total_goals \
            FROM {table_name} \
            WHERE event_type = 'goal' AND minute BETWEEN {m1} AND {m2};",
    "exp": "Filter goal events between the given minute window and count them.",
    "variables": ["table_name", "m1", "m2"],
    "paraphrases": [
    "How many goals were scored from minute {m1} to {m2}?",
    "Give the total goal count during the time period {m1}–{m2}.",
    "Count all goals scored within the minutes {m1}–{m2}."
    ]
    },
    {
    "id": 10,
    "question": "Which player received the earliest yellow card?",
    "query": "SELECT player, minute \
            FROM {table_name} \
            WHERE event_type = 'yellow_card' \
            ORDER BY minute ASC \
            LIMIT 1;",
    "exp": "Return the earliest yellow card event in the match.",
    "variables": ["table_name"],
    "paraphrases": [
    "Who was booked first in the match?",
    "Identify the player who received the first yellow card.",
    "Which player got the earliest caution?"
    ]
    },
    {
    "id": 11,
    "question": "Show each player's attacking contribution in terms of goals, shots, and crosses.",
    "query": "SELECT \
                player, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END)    AS goals, \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END)    AS shots, \
                SUM(CASE WHEN event_type = 'cross' THEN 1 ELSE 0 END)   AS crosses \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                GROUP BY player \
                ORDER BY goals DESC, shots DESC, crosses DESC;",
    "exp": "Aggregate events per player and compute counts of goals, shots, and crosses. Return a table of all players with their attacking stats.",
    "variables": ["table_name"],
    "paraphrases": [
        "Give me a table of all players with how many goals, shots, and crosses they had.",
        "List every player along with their counts of goals, shots, and crosses in the match.",
        "Show per-player attacking stats: goals, shots, and crosses for everyone."
    ]
    },
    {
    "id": 12,
    "question": "Show a summary of goals, corners, free kicks, and yellow cards for each team.",
    "query": "SELECT \
                team, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END)         AS goals, \
                SUM(CASE WHEN event_type = 'corner' THEN 1 ELSE 0 END)       AS corners, \
                SUM(CASE WHEN event_type = 'free_kick' THEN 1 ELSE 0 END)    AS free_kicks, \
                SUM(CASE WHEN event_type = 'yellow_card' THEN 1 ELSE 0 END)  AS yellow_cards \
                FROM {table_name} \
                WHERE team IS NOT NULL AND team <> '' \
                GROUP BY team \
                ORDER BY goals DESC, corners DESC;",
    "exp": "Group all events by team and compute counts of key event types (goals, corners, free kicks, yellow cards) for each team.",
    "variables": ["table_name"],
    "paraphrases": [
        "Provide a table per team showing their goals, corners, free kicks, and yellow cards.",
        "Summarize the major event statistics (goals, corners, free kicks, yellows) for each team.",
        "List each team with how many goals, corners, free kicks, and yellow cards they had."
    ]
    },
    {
    "id": 13,
    "question": "List all goals scored in the match with minute, team, player, and description.",
    "query": "SELECT \
                minute, team, player, description \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                ORDER BY minute ASC, event_id ASC;",
    "exp": "Filter to only goal events and show when they happened, who scored, and for which team, ordered by match time.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show a chronological table of all goals with the minute, scoring team, scorer, and commentary.",
        "List every goal in the match along with its time, team, player, and description.",
        "Provide all goal events with full details in order of occurrence."
    ]
    },
    {
    "id": 14,
    "question": "Show all events that occurred between minute {m1} and {m2}.",
    "query": "SELECT \
                minute, event_type, team, player, description \
                FROM {table_name} \
                WHERE minute BETWEEN {m1} AND {m2} \
                ORDER BY minute ASC, event_id ASC;",
    "exp": "Return a detailed timeline of every event within the specified minute window, preserving chronological order.",
    "variables": ["table_name", "m1", "m2"],
    "paraphrases": [
        "Give me the full event log from minute {m1} to minute {m2}.",
        "List all events that happened between {m1}' and {m2}', with their types and details.",
        "Show a chronological table of events occurring in the time range {m1}–{m2}."
    ]
    },
    {
    "id": 15,
    "question": "List all substitutions made in the match with minute, team, and player.",
    "query": "SELECT \
                minute, team, player, description \
                FROM {table_name} \
                WHERE event_type = 'substitution' \
                ORDER BY minute ASC, event_id ASC;",
    "exp": "Filter substitution events and show when they occurred, which team made the change, and which player is referenced in the commentary.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show all substitution events in the match in chronological order.",
        "List every substitution with minute, team, player mentioned, and the commentary.",
        "Provide a table of all substitutions, ordered by when they happened."
    ]
    },
    {
    "id": 16,
    "question": "For each minute, how many events occurred, and which minutes were the busiest?",
    "query": "SELECT \
                minute, \
                COUNT(*) AS total_events \
                FROM {table_name} \
                GROUP BY minute \
                ORDER BY total_events DESC, minute ASC;",
    "exp": "Count how many events happened in each minute of the match and list all minutes ordered by event volume.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show a table of minutes and the number of events in each, sorted by the busiest minutes first.",
        "For each match minute, list how many events took place, ordered from most to least active.",
        "Give a per-minute breakdown of event counts, highlighting which minutes saw the most action."
    ]
    },
    {
    "id": 17,
    "question": "Show, for each team and event type, how many times that event occurred.",
    "query": "SELECT \
                team, \
                event_type, \
                COUNT(*) AS event_count \
                FROM {table_name} \
                WHERE team IS NOT NULL AND team <> '' \
                GROUP BY team, event_type \
                ORDER BY team ASC, event_count DESC;",
    "exp": "Group by both team and event_type to produce a matrix-like table showing how frequently each team triggered each event type.",
    "variables": ["table_name"],
    "paraphrases": [
        "Provide a table of all teams and event types with how many times each event happened per team.",
        "Show the distribution of event types per team, listing counts for every team–event_type pair.",
        "List, for each team, how often each kind of event (goal, corner, cross, etc.) occurred."
    ]
    },
    {
    "id": 18,
    "question": "List all events in which {player} was involved, in match order.",
    "query": "SELECT \
                minute, event_type, team, player, description \
                FROM {table_name} \
                WHERE player = '{player}' \
                ORDER BY minute ASC, event_id ASC;",
    "exp": "Filter the full event log to only show rows where the given player appears, returning their complete involvement timeline.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Show every event that involved {player}, in chronological order.",
        "Give me the full event history for {player} with minute, event type, team, and description.",
        "List all match actions where {player} is mentioned, ordered by minute."
    ]
    },
    {
    "id": 19,
    "question": "Which players attempted at least {min_shots} shots and at least {min_crosses} crosses?",
    "query": "SELECT \
                player, \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END)  AS total_shots, \
                SUM(CASE WHEN event_type = 'cross' THEN 1 ELSE 0 END) AS total_crosses \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                GROUP BY player \
                HAVING \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END)  >= {min_shots} AND \
                SUM(CASE WHEN event_type = 'cross' THEN 1 ELSE 0 END) >= {min_crosses} \
                ORDER BY total_shots DESC, total_crosses DESC;",
    "exp": "Aggregate per player, count their shots and crosses, then keep only players who meet both minimum thresholds.",
    "variables": ["table_name", "min_shots", "min_crosses"],
    "paraphrases": [
        "List all players who had at least {min_shots} shots and {min_crosses} crosses.",
        "Which players were heavily involved in attack with at least {min_shots} shots and {min_crosses} crosses?",
        "Show the players who combined a minimum of {min_shots} shot attempts and {min_crosses} crosses."
    ]
    },
    {
    "id": 20,
    "question": "Which players both scored a goal and received a yellow card?",
    "query": "SELECT \
                player, \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END)        AS goals, \
                SUM(CASE WHEN event_type = 'yellow_card' THEN 1 ELSE 0 END) AS yellow_cards \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                AND event_type IN ('goal', 'yellow_card') \
                GROUP BY player \
                HAVING \
                SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) > 0 AND \
                SUM(CASE WHEN event_type = 'yellow_card' THEN 1 ELSE 0 END) > 0 \
                ORDER BY goals DESC, yellow_cards DESC;",
    "exp": "Find players who appear in at least one goal event and at least one yellow_card event, and show both counts.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show all players who both scored and were booked with a yellow card.",
        "Which players managed to score a goal but also picked up a yellow card?",
        "List the players who have at least one goal and at least one yellow card in this match."
    ]
    },
    {
    "id": 21,
    "question": "Which players were involved in events in both the first and second halves of the match?",
    "query": "SELECT \
                player, \
                MIN(minute) AS first_involvement_minute, \
                MAX(minute) AS last_involvement_minute \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                GROUP BY player \
                HAVING \
                SUM(CASE WHEN minute < 46 THEN 1 ELSE 0 END)  > 0 AND \
                SUM(CASE WHEN minute >= 46 THEN 1 ELSE 0 END) > 0 \
                ORDER BY first_involvement_minute ASC;",
    "exp": "Group events by player and keep only those who appear at least once before minute 46 and at least once from minute 46 onwards.",
    "variables": ["table_name"],
    "paraphrases": [
        "List players who had events in both the first half and the second half.",
        "Which players were active on the event log in each half of the match?",
        "Show all players involved before and after half-time."
    ]
    },
    {
    "id": 22,
    "question": "Which players had attacking actions (shots, crosses, or goals) after minute {start_minute}?",
    "query": "SELECT \
                player, \
                SUM(CASE WHEN event_type = 'goal'  THEN 1 ELSE 0 END) AS goals, \
                SUM(CASE WHEN event_type = 'shot'  THEN 1 ELSE 0 END) AS shots, \
                SUM(CASE WHEN event_type = 'cross' THEN 1 ELSE 0 END) AS crosses \
                FROM {table_name} \
                WHERE minute > {start_minute} \
                AND event_type IN ('goal', 'shot', 'cross') \
                AND player IS NOT NULL AND player <> '' \
                GROUP BY player \
                HAVING \
                SUM(CASE WHEN event_type IN ('goal','shot','cross') THEN 1 ELSE 0 END) > 0 \
                ORDER BY goals DESC, shots DESC, crosses DESC;",
    "exp": "Consider only attacking events after a given minute and list all players who were involved, with their counts of goals, shots, and crosses.",
    "variables": ["table_name", "start_minute"],
    "paraphrases": [
        "Show all players who contributed attacking actions (shots, crosses, goals) after minute {start_minute}.",
        "Which players were involved in attack late in the match, after {start_minute}'?",
        "List the players with shots, crosses, or goals in the period after minute {start_minute}."
    ]
    },
    {
    "id": 23,
    "question": "What is the total number of events that occurred {temporal_phrase} of the match?",
    "query": "SELECT COUNT(*) AS total_events FROM {table_name} WHERE {temporal_predicate};",
    "exp": "Filter all events whose minute satisfies {temporal_predicate}, and count the total number of events in that period.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many events took place in total during {temporal_phrase}?",
        "Calculate the aggregate number of events from {temporal_phrase}.",
        "What is the total event count in the period {temporal_phrase} of the match?"
    ]
    },
    {
    "id": 24,
    "question": "Find the player who has scored the most goals in the entire match and how many of those goals were scored {temporal_phrase}?",
    "query": "WITH top_scorer AS ( \
                SELECT player, COUNT(*) AS total_goals \
                FROM {table_name} \
                WHERE event_type = 'goal' AND player IS NOT NULL AND player <> '' \
                GROUP BY player \
                ORDER BY total_goals DESC \
                LIMIT 1 \
                ), \
                goals_in_range AS ( \
                SELECT COUNT(*) AS goals_in_range \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                    AND player = (SELECT player FROM top_scorer) \
                    AND {temporal_predicate} \
                ) \
                SELECT \
                (SELECT player FROM top_scorer)       AS player, \
                (SELECT total_goals FROM top_scorer) AS total_goals_overall, \
                (SELECT goals_in_range FROM goals_in_range) AS goals_scored_in_range;",
    "exp": "First, find the top goal scorer across the whole match. Then, for that same player, count how many goals they scored during the period defined by {temporal_predicate}.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Who was the top scorer overall, and how many of their goals came during {temporal_phrase}?",
        "In the entire match, which player scored the most goals, and how many of those were scored in {temporal_phrase}?",
        "Identify the leading goal scorer and report how many goals they scored specifically during {temporal_phrase}."
    ]
    },
    {
    "id": 25,
    "question": "Which player attempted the most shots in the entire match and how many of those shots were taken {temporal_phrase}?",
    "query": "SELECT \
                player, \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END) AS total_shots, \
                SUM(CASE WHEN event_type = 'shot' AND {temporal_predicate} THEN 1 ELSE 0 END) AS shots_in_range \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                GROUP BY player \
                HAVING \
                SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END) = ( \
                    SELECT MAX(total_shots_all) \
                    FROM ( \
                    SELECT SUM(CASE WHEN event_type = 'shot' THEN 1 ELSE 0 END) AS total_shots_all \
                    FROM {table_name} \
                    WHERE player IS NOT NULL AND player <> '' \
                    GROUP BY player \
                    ) t \
                );",
    "exp": "Find the player with the highest total number of shots across the match, then compute how many of their shots occurred during the time span described by {temporal_predicate}.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "During the whole match, which player took the most shots, and how many of those came {temporal_phrase}?",
        "Who was the most frequent shooter overall, and what was their shot count in {temporal_phrase}?",
        "Identify the player with the most shot attempts and state how many they took during {temporal_phrase}."
    ]
    },
    {
    "id": 26,
    "question": "When did {team} score their first goal {temporal_phrase}?",
    "query": "SELECT minute \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND event_type = 'goal' \
                AND {temporal_predicate} \
                ORDER BY minute ASC \
                LIMIT 1;",
    "exp": "Within the period defined by {temporal_predicate}, find the earliest minute in which {team} scored a goal.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "{temporal_phrase}, at what minute did {team} score their first goal?",
        "For {team}, when did their opening goal occur during {temporal_phrase}?",
        "Can you tell me the first goal minute for {team} within {temporal_phrase}?"
    ]
    },
    {
    "id": 27,
    "question": "How many corners did {team} take {temporal_phrase}? Show the tally in a table.",
    "query": "SELECT COUNT(*) AS total_corners \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND event_type = 'corner' \
                AND {temporal_predicate};",
    "exp": "Count the number of corner events taken by {team} during the time window specified by {temporal_predicate}.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Please provide a table showing how many corners {team} took {temporal_phrase}.",
        "Show me the total number of corners awarded to {team} during {temporal_phrase}.",
        "What's the count of corner kicks taken by {team} in the period {temporal_phrase}?"
    ]
    },
    {
    "id": 28,
    "question": "What is the total number of goals scored by {team1} and {team2} combined {temporal_phrase}?",
    "query": "SELECT COUNT(*) AS total_goals_combined \
                FROM {table_name} \
                WHERE team IN ('{team1}', '{team2}') \
                AND event_type = 'goal' \
                AND {temporal_predicate};",
    "exp": "Filter goal events belonging to either {team1} or {team2} in the period {temporal_predicate}, and count them.",
    "variables": ["table_name", "team1", "team2", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "{temporal_phrase}, how many goals did {team1} and {team2} score together?",
        "What's the combined goal tally of {team1} and {team2} during {temporal_phrase}?",
        "Provide the total number of goals scored by both {team1} and {team2} in the period {temporal_phrase}."
    ]
    },
    {
    "id": 29,
    "question": "Who was involved in the most total events in the entire match and in how many events were they involved {temporal_phrase}?",
    "query": "SELECT \
                player, \
                COUNT(*) AS total_events_in_match, \
                SUM(CASE WHEN {temporal_predicate} THEN 1 ELSE 0 END) AS events_in_range \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                GROUP BY player \
                HAVING COUNT(*) = ( \
                SELECT MAX(event_count) \
                FROM ( \
                    SELECT COUNT(*) AS event_count \
                    FROM {table_name} \
                    WHERE player IS NOT NULL AND player <> '' \
                    GROUP BY player \
                ) t \
                );",
    "exp": "Find the player with the highest total number of events across the match, then compute how many of those events occurred during {temporal_phrase}.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Across the full match, which player appeared in the most events, and how many of those were during {temporal_phrase}?",
        "Who had the highest overall event involvement, and what was their event count in {temporal_phrase}?",
        "Identify the player with the most event participations and state how many of those occurred during {temporal_phrase}."
    ]
    },
    {
    "id": 30,
    "question": "How many goals did {player} score {temporal_phrase}?",
    "query": "SELECT COUNT(*) AS total_goals_player \
                FROM {table_name} \
                WHERE player = '{player}' \
                AND event_type = 'goal' \
                AND {temporal_predicate};",
    "exp": "Count the number of goal events attributed to {player} during the period defined by {temporal_predicate}.",
    "variables": ["table_name", "player", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What was {player}'s goal tally during {temporal_phrase}?",
        "How many goals did {player} score in the time span {temporal_phrase}?",
        "Could you tell me the total number of goals scored by {player} {temporal_phrase}?"
    ]
    },
    {
    "id": 31,
    "question": "What is the average number of events per active minute for {team} {temporal_phrase}?",
    "query": "SELECT \
                CASE WHEN COUNT(DISTINCT minute) = 0 \
                    THEN 0 \
                    ELSE CAST(COUNT(*) AS FLOAT) / COUNT(DISTINCT minute) \
                END AS avg_events_per_minute \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND {temporal_predicate};",
    "exp": "For the given team and period {temporal_predicate}, compute the total number of events divided by the number of distinct minutes in which they had at least one event.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "During {temporal_phrase}, what is the average number of events per minute for {team} (considering only minutes where they had an event)?",
        "Calculate the mean events per active minute for {team} in the period {temporal_phrase}.",
        "On average, how many events did {team} generate per minute during {temporal_phrase}?"
    ]
    },
    {
    "id": 32,
    "question": "How many goals were scored in total {temporal_phrase}?",
    "query": "SELECT COUNT(*) AS total_goals \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                AND {temporal_predicate};",
    "exp": "Filter only goal events whose minute satisfies {temporal_predicate} and count the total number of goals in that time period.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What's the grand total of goals scored during {temporal_phrase}?",
        "Could you tell me how many goals were scored in the period {temporal_phrase}?",
        "How many times did the ball hit the net during {temporal_phrase}?"
    ]
    },
    {
    "id": 33,
    "question": "Which team scored the most goals and received the fewest yellow cards {temporal_phrase}, and what were their counts?",
    "query": "SELECT \
                team, \
                SUM(CASE WHEN event_type = 'goal'        THEN 1 ELSE 0 END) AS total_goals, \
                SUM(CASE WHEN event_type = 'yellow_card' THEN 1 ELSE 0 END) AS total_yellows \
                FROM {table_name} \
                WHERE team IS NOT NULL AND team <> '' \
                AND {temporal_predicate} \
                GROUP BY team \
                ORDER BY total_goals DESC, total_yellows ASC \
                LIMIT 1;",
    "exp": "Within {temporal_predicate}, for each team, count goals and yellow cards. Then select the team with the highest goal count, breaking ties by the fewest yellow cards.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "{temporal_phrase}, which team combined the most goals with the fewest yellow cards, and what were those numbers?",
        "During {temporal_phrase}, identify the team that scored the most while picking up the least bookings, and provide their goals and yellow-card counts.",
        "Find the team with the best mix of high scoring and discipline in {temporal_phrase}, and state their goals and yellow cards."
    ]
    },
    {
    "id": 34,
    "question": "Calculate the total number of crosses attempted by all players from {team} {temporal_phrase}.",
    "query": "SELECT COUNT(*) AS total_crosses \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND event_type = 'cross' \
                AND {temporal_predicate};",
    "exp": "Count all cross events taken by the specified team during the period defined by {temporal_predicate}.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many crosses did {team} attempt during {temporal_phrase}?",
        "Can you sum up all the crosses made by {team} in the period {temporal_phrase}?",
        "What's the cumulative count of crosses played by {team} during {temporal_phrase}?"
    ]
    },
    {
    "id": 35,
    "question": "Calculate the total number of yellow cards shown to players of {team} {temporal_phrase}.",
    "query": "SELECT COUNT(*) AS total_yellow_cards \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND event_type = 'yellow_card' \
                AND {temporal_predicate};",
    "exp": "Count yellow-card events where the team is {team} and the minute satisfies {temporal_predicate}.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What's the total number of yellow cards received by {team} during {temporal_phrase}?",
        "How many bookings did players from {team} get in the period {temporal_phrase}?",
        "Provide the number of yellow cards shown to {team}'s players during {temporal_phrase}."
    ]
    },
    {
    "id": 36,
    "question": "Calculate the total number of offside calls against {team} {temporal_phrase}.",
    "query": "SELECT COUNT(*) AS total_offsides \
                FROM {table_name} \
                WHERE team = '{team}' \
                AND event_type = 'offside' \
                AND {temporal_predicate};",
    "exp": "Count all offside events associated with {team} during the period defined by {temporal_predicate}.",
    "variables": ["table_name", "team", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many offside decisions went against {team} during {temporal_phrase}?",
        "Can you tell me the total offside calls for {team} in the period {temporal_phrase}?",
        "What's the number of offsides committed by {team} during {temporal_phrase}?"
    ]
    },
    {
    "id": 37,
    "question": "How many total events was {player} involved in during the match?",
    "query": "SELECT COUNT(*) AS total_events \
                FROM {table_name} \
                WHERE player = '{player}';",
    "exp": "Count all rows where the player field matches {player}, indicating their total event involvements.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "How many events featured {player}?",
        "What is the total number of actions involving {player}?",
        "Count all the events in which {player} appears."
    ]
    },
    {
    "id": 38,
    "question": "What types of events did {player} participate in, and how many times for each type?",
    "query": "SELECT event_type, COUNT(*) AS event_count \
                FROM {table_name} \
                WHERE player = '{player}' \
                GROUP BY event_type \
                ORDER BY event_count DESC;",
    "exp": "Group all events involving {player} by event_type and count each type.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Give a breakdown of all event types {player} was involved in.",
        "List how many times {player} appeared in each event category.",
        "Show the event distribution of {player} by type."
    ]
    },
    {
    "id": 39,
    "question": "List all attacking actions—shots, crosses, and goals—performed by {player}.",
    "query": "SELECT minute, event_type, description \
                FROM {table_name} \
                WHERE player = '{player}' \
                AND event_type IN ('shot', 'cross', 'goal') \
                ORDER BY minute ASC;",
    "exp": "Filter all attacking events for {player} and return them chronologically.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Show all of {player}'s attacking contributions: shots, crosses, and goals.",
        "List the offensive actions made by {player}.",
        "Give me a chronological log of {player}'s shots, crosses, and goals."
    ]
    },
    {
    "id": 40,
    "question": "How many crosses did {player} attempt?",
    "query": "SELECT COUNT(*) AS total_crosses \
                FROM {table_name} \
                WHERE player = '{player}' AND event_type = 'cross';",
    "exp": "Count all crossing events attributed to the specified player.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "How many crossing attempts were made by {player}?",
        "Count the total crosses delivered by {player}.",
        "What is the number of crosses played by {player}?"
    ]
    },
    {
    "id": 41,
    "question": "How many shots did {player} take during the match?",
    "query": "SELECT COUNT(*) AS total_shots \
                FROM {table_name} \
                WHERE player = '{player}' AND event_type = 'shot';",
    "exp": "Count the total number of shot events performed by {player}.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "How many shot attempts were made by {player}?",
        "Count all shooting events involving {player}.",
        "What is the total number of shots taken by {player}?"
    ]
    },
    {
    "id": 42,
    "question": "How many yellow cards did {player} receive?",
    "query": "SELECT COUNT(*) AS yellow_cards \
                FROM {table_name} \
                WHERE player = '{player}' AND event_type = 'yellow_card';",
    "exp": "Count all yellow-card events for {player}.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Did {player} get booked, and how many times?",
        "How many yellow cards were shown to {player}?",
        "Count the number of cautions given to {player}."
    ]
    },
    {
    "id": 45,
    "question": "List all minute-by-minute actions involving {player}.",
    "query": "SELECT minute, event_type, description \
                FROM {table_name} \
                WHERE player = '{player}' \
                ORDER BY minute ASC, event_id ASC;",
    "exp": "Return every event row where {player} is involved, in chronological order.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Show the full chronological log of events involving {player}.",
        "Give me every match action {player} took part in.",
        "List all events referencing {player} in order."
    ]
    },
    {
    "id": 46,
    "question": "What was the first event involving {player}?",
    "query": "SELECT minute, event_type, description \
                FROM {table_name} \
                WHERE player = '{player}' \
                ORDER BY minute ASC, event_id ASC \
                LIMIT 1;",
    "exp": "Return the earliest match event in which {player} appears.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "At what moment did {player} first appear in the event log?",
        "What was {player}'s first recorded action in the match?",
        "Identify the earliest event involving {player}."
    ]
    },
    {
    "id": 47,
    "question": "What was the last event involving {player}?",
    "query": "SELECT minute, event_type, description \
                FROM {table_name} \
                WHERE player = '{player}' \
                ORDER BY minute DESC, event_id DESC \
                LIMIT 1;",
    "exp": "Return the final event by minute where {player} appears.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "What is the most recent action in the match involving {player}?",
        "What was the final recorded event for {player}?",
        "Show the last appearance of {player} in the event timeline."
    ]
    },
    {
    "id": 48,
    "question": "Was {player} involved in any substitutions (on or off)? Show the events.",
    "query": "SELECT minute, team, description \
                FROM {table_name} \
                WHERE event_type = 'substitution' \
                AND description LIKE '%' || '{player}' || '%' \
                ORDER BY minute ASC;",
    "exp": "Match substitution events whose commentary text mentions {player}, capturing both 'comes on' and 'goes off'.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "List substitution events referencing {player}.",
        "Was {player} subbed on or off? Show all relevant events.",
        "Find substitution descriptions that include {player}'s name."
    ]
    },
    {
    "id": 49,
    "question": "Did {player} create any set-piece opportunities (corners or free kicks)?",
    "query": "SELECT minute, event_type, description \
                FROM {table_name} \
                WHERE player = '{player}' \
                AND event_type IN ('corner', 'free_kick') \
                ORDER BY minute ASC;",
    "exp": "Return all corner or free-kick events attributed to {player}.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "List all corners or free kicks involving {player}.",
        "Did {player} contribute to any set-piece events?",
        "Show every time {player} took or created a corner/free-kick situation."
    ]
    },
    {
    "id": 50,
    "question": "How many offsides was {player} involved in?",
    "query": "SELECT COUNT(*) AS total_offsides \
                FROM {table_name} \
                WHERE player = '{player}' \
                AND event_type = 'offside';",
    "exp": "Count all offside calls involving the specified player.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "How many times was {player} flagged offside?",
        "Count the offside events {player} committed.",
        "What is the total number of offsides for {player}?"
    ]
    },
    {
    "id": 51,
    "question": "In which minutes was {player} most active?",
    "query": "SELECT minute, COUNT(*) AS events_in_minute \
                FROM {table_name} \
                WHERE player = '{player}' \
                GROUP BY minute \
                ORDER BY events_in_minute DESC, minute ASC;",
    "exp": "Group events by minute for {player} to find activity peaks.",
    "variables": ["table_name", "player"],
    "paraphrases": [
        "Show the busiest minutes for {player}.",
        "During which minutes did {player} appear the most?",
        "List minute-by-minute event density for {player}."
    ]
    },
    {
    "id": 52,
    "question": "Who was the top goal scorer in the match, and how many total attacking actions (goals, shots, crosses) did that player have?",
    "query": "WITH goal_counts AS ( \
                SELECT player, COUNT(*) AS total_goals \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                    AND player IS NOT NULL AND player <> '' \
                GROUP BY player \
                ), \
                top_scorer AS ( \
                SELECT player, total_goals \
                FROM goal_counts \
                WHERE total_goals = (SELECT MAX(total_goals) FROM goal_counts) \
                LIMIT 1 \
                ) \
                SELECT \
                ts.player, \
                ts.total_goals, \
                SUM(CASE WHEN t.event_type IN ('goal','shot','cross') THEN 1 ELSE 0 END) AS total_attacking_actions \
                FROM {table_name} t \
                JOIN top_scorer ts \
                ON t.player = ts.player \
                GROUP BY ts.player, ts.total_goals;",
    "exp": "First compute total goals per player and pick the top scorer. Then, for that player, count all attacking actions (goals, shots, crosses) across the full match.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player scored the most goals, and how many total attacking actions (shots, crosses, goals) did they contribute?",
        "Find the top goal scorer and report their combined number of goals, shots, and crosses.",
        "Who was the leading scorer, and what was their overall attacking involvement in terms of events?"
    ]
    },
    {
    "id": 53,
    "question": "Which team scored the most goals, and which players from that team attempted at least one shot?",
    "query": "WITH team_goals AS ( \
                SELECT team, COUNT(*) AS total_goals \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                    AND team IS NOT NULL AND team <> '' \
                GROUP BY team \
                ), \
                top_team AS ( \
                SELECT team, total_goals \
                FROM team_goals \
                WHERE total_goals = (SELECT MAX(total_goals) FROM team_goals) \
                LIMIT 1 \
                ) \
                SELECT \
                t.player, \
                COUNT(*) AS total_shots \
                FROM {table_name} t \
                WHERE t.team = (SELECT team FROM top_team) \
                AND t.event_type = 'shot' \
                AND t.player IS NOT NULL AND t.player <> '' \
                GROUP BY t.player \
                ORDER BY total_shots DESC, t.player ASC;",
    "exp": "First identify the team with the highest number of goals. Then, within that team, list all players who took at least one shot and count how many shots each took.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team scored the most, and which players from that team recorded shots?",
        "Find the highest-scoring team and list all its shooters with their shot counts.",
        "Identify the top scoring team and show which players from that team attempted shots."
    ]
    },
    {
    "id": 54,
    "question": "Who received the earliest yellow card in the match, and what actions did that player take after being booked?",
    "query": "WITH earliest_booking AS ( \
                SELECT player, minute \
                FROM {table_name} \
                WHERE event_type = 'yellow_card' \
                    AND player IS NOT NULL AND player <> '' \
                ORDER BY minute ASC, event_id ASC \
                LIMIT 1 \
                ) \
                SELECT \
                t.minute, \
                t.event_type, \
                t.team, \
                t.description \
                FROM {table_name} t \
                JOIN earliest_booking eb \
                ON t.player = eb.player \
                WHERE t.minute > eb.minute \
                ORDER BY t.minute ASC, t.event_id ASC;",
    "exp": "First find the player who got the earliest yellow card. Then list all subsequent events involving that same player after the booking.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the player who was booked first and show everything they did after that booking.",
        "Who received the earliest yellow card, and what were their later actions in the match?",
        "Find the earliest booked player and list their post-booking event timeline."
    ]
    },
    {
    "id": 55,
    "question": "Which player from the team that conceded the first goal took the most shots in the match?",
    "query": "WITH first_goal AS ( \
                SELECT minute, team \
                FROM {table_name} \
                WHERE event_type = 'goal' \
                    AND team IS NOT NULL AND team <> '' \
                ORDER BY minute ASC, event_id ASC \
                LIMIT 1 \
                ), \
                conceding_team AS ( \
                SELECT DISTINCT t2.team AS team \
                FROM {table_name} t1 \
                JOIN {table_name} t2 \
                    ON 1 = 1 \
                WHERE t1.event_type = 'goal' \
                    AND t1.team = (SELECT team FROM first_goal) \
                    AND t2.team <> t1.team \
                    AND t2.team IS NOT NULL AND t2.team <> '' \
                LIMIT 1 \
                ), \
                team_shots AS ( \
                SELECT player, COUNT(*) AS total_shots \
                FROM {table_name} \
                WHERE team = (SELECT team FROM conceding_team) \
                    AND event_type = 'shot' \
                    AND player IS NOT NULL AND player <> '' \
                GROUP BY player \
                ) \
                SELECT player, total_shots \
                FROM team_shots \
                WHERE total_shots = (SELECT MAX(total_shots) FROM team_shots);",
    "exp": "First find the team that scored the first goal. Then infer the opposing (conceding) team and among its players, find who took the most shots.",
    "variables": ["table_name"],
    "paraphrases": [
        "From the team that conceded the first goal, which player fired the most shots?",
        "Who was the main shooter on the side that let in the opening goal?",
        "Identify the player with the most shot attempts from the team that conceded first."
    ]
    },
    {
    "id": 56,
    "question": "For the team that made the first substitution, which players from that team recorded attacking actions (shots, crosses, or goals) after that substitution?",
    "query": "WITH first_sub AS ( \
                SELECT minute, team \
                FROM {table_name} \
                WHERE event_type = 'substitution' \
                    AND team IS NOT NULL AND team <> '' \
                ORDER BY minute ASC, event_id ASC \
                LIMIT 1 \
                ) \
                SELECT \
                t.player, \
                SUM(CASE WHEN t.event_type IN ('goal','shot','cross') THEN 1 ELSE 0 END) AS attacking_actions \
                FROM {table_name} t \
                WHERE t.team = (SELECT team FROM first_sub) \
                AND t.minute > (SELECT minute FROM first_sub) \
                AND t.player IS NOT NULL AND t.player <> '' \
                AND t.event_type IN ('goal','shot','cross') \
                GROUP BY t.player \
                ORDER BY attacking_actions DESC, t.player ASC;",
    "exp": "Determine which team made the first substitution. Then, after that minute, list all players from that team who produced attacking actions and count those actions.",
    "variables": ["table_name"],
    "paraphrases": [
        "After the earliest substitution in the match, which players from that team contributed shots, crosses, or goals?",
        "For the team that subbed first, who was involved in attacking moves after the change?",
        "List attackers from the first-subbing team and their attacking actions after that substitution."
    ]
    },
    {
    "id": 57,
    "question": "Which player had the highest combined count of crosses and shots, and for which team did they play?",
    "query": "WITH player_attacks AS ( \
                SELECT \
                    player, \
                    team, \
                    SUM(CASE WHEN event_type = 'cross' THEN 1 ELSE 0 END) AS total_crosses, \
                    SUM(CASE WHEN event_type = 'shot'  THEN 1 ELSE 0 END) AS total_shots \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                GROUP BY player, team \
                ), \
                totals AS ( \
                SELECT \
                    player, \
                    team, \
                    total_crosses, \
                    total_shots, \
                    (total_crosses + total_shots) AS combined_attacks \
                FROM player_attacks \
                ) \
                SELECT \
                player, \
                team, \
                total_crosses, \
                total_shots, \
                combined_attacks \
                FROM totals \
                WHERE combined_attacks = (SELECT MAX(combined_attacks) FROM totals);",
    "exp": "First compute crosses and shots per player-team pair. Then compute the sum of these attacking actions and select the player with the highest combined total.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player led the match in combined crosses and shots, and what team were they on?",
        "Find the player with the greatest sum of crosses plus shots and report their team.",
        "Identify the player who most frequently shot or crossed, along with their team and counts."
    ]
    },
    {
    "id": 58,
    "question": "Among players who scored at least one goal, count their yellow cards and which of them had the most total events in the match?",
    "query": "WITH goal_scorers AS ( \
                SELECT player \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                GROUP BY player \
                HAVING SUM(CASE WHEN event_type = 'goal' THEN 1 ELSE 0 END) > 0 \
                ), \
                player_stats AS ( \
                SELECT \
                    t.player, \
                    SUM(CASE WHEN t.event_type = 'yellow_card' THEN 1 ELSE 0 END) AS yellow_cards, \
                    COUNT(*) AS total_events \
                FROM {table_name} t \
                JOIN goal_scorers g \
                    ON t.player = g.player \
                GROUP BY t.player \
                ) \
                SELECT \
                player, \
                yellow_cards, \
                total_events \
                FROM player_stats \
                WHERE total_events = (SELECT MAX(total_events) FROM player_stats);",
    "exp": "First, identify all players who scored at least one goal in the match. Then, for this subset of goal scorers, compute two things for each player: the number of yellow cards they received and their total number of events. Finally, return the player(s) among them with the highest total event count, along with their yellow-card count.",
    "variables": ["table_name"],
    "paraphrases": [
        "Among all goal scorers, how many yellow cards did each receive, and which had the most overall events?",
        "For players who scored at least once, report their yellow-card tally and identify who was most active in terms of total events.",
        "From the set of goal scorers, count yellow cards per player and find the one with the highest event involvement." 
    ]
    },
    {
    "id": 59,
    "question": "Which player had the highest number of 'influence chains'? A players influence chain is defined as each case where an event involving that player (of any event_type) is immediately followed in the event log by the very next event in the match that (a) occurs within at most 1 match minute of the player’s event and (b) is an attacking event of type 'shot', 'cross', or 'goal' by any team. Count, for each player, how many such influence chains they have and return the player(s) with the maximum count.",
    "query": "WITH base AS ( \
                SELECT event_id, minute, team, player, event_type \
                FROM {table_name} \
                ), \
                next_event AS ( \
                SELECT \
                    b1.event_id AS base_event_id, \
                    b1.player   AS base_player, \
                    b1.team     AS base_team, \
                    b1.minute   AS base_minute, \
                    (SELECT b2.event_id \
                    FROM {table_name} b2 \
                    WHERE (b2.minute > b1.minute \
                            OR (b2.minute = b1.minute AND b2.event_id > b1.event_id)) \
                    ORDER BY b2.minute, b2.event_id \
                    LIMIT 1) AS next_event_id \
                FROM base b1 \
                WHERE b1.player IS NOT NULL AND b1.player <> '' \
                ), \
                chains AS ( \
                SELECT \
                    ne.base_player AS player, \
                    ne.base_team   AS team, \
                    COUNT(*)       AS influence_chains \
                FROM next_event ne \
                JOIN {table_name} n \
                    ON n.event_id = ne.next_event_id \
                WHERE n.event_type IN ('shot','cross','goal') \
                    AND n.minute - ne.base_minute BETWEEN 0 AND 1 \
                GROUP BY ne.base_player, ne.base_team \
                ) \
                SELECT player, team, influence_chains \
                FROM chains \
                WHERE influence_chains = (SELECT MAX(influence_chains) FROM chains);",
    "exp": "First, consider every event where a player is present. For each such event, find the very next event in the match (based on minute and event_id ordering). If that next event is an attacking event ('shot', 'cross', or 'goal') and occurs within at most 1 minute of the player’s event, we count that as one influence chain for the player who triggered the original event. We then sum these influence chains per player and return the player(s) with the highest total.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player most often had their actions immediately followed by an attacking event within one minute?",
        "Identify the player whose events most frequently led directly to a shot, cross, or goal as the next event in the log.",
        "Who generated the largest number of immediate attacking follow-ups (influence chains) after their actions?"
    ]
    },
    {
    "id": 60,
    "question": "Which team produced the highest number of 'pressure sequences'? A pressure sequence for a team is defined as any window starting from a given attacking event (shot, cross, or corner) by that team where, within the next 2 match minutes (including the starting minute), that same team records at least 3 attacking events of types 'shot', 'cross', or 'corner' (we count one pressure sequence per starting attacking event that satisfies this condition, even if windows overlap). Count how many such pressure sequences each team has and return the team(s) with the maximum count.",
    "query": "WITH attacking_events AS ( \
                SELECT event_id, minute, team \
                FROM {table_name} \
                WHERE event_type IN ('shot','cross','corner') \
                    AND team IS NOT NULL AND team <> '' \
                ), \
                windows AS ( \
                SELECT \
                    a.team, \
                    a.event_id, \
                    a.minute, \
                    (SELECT COUNT(*) \
                    FROM {table_name} t \
                    WHERE t.team = a.team \
                    AND t.event_type IN ('shot','cross','corner') \
                    AND t.minute BETWEEN a.minute AND a.minute + 2) AS window_attacks \
                FROM attacking_events a \
                ), \
                pressure AS ( \
                SELECT team, COUNT(*) AS pressure_sequences \
                FROM windows \
                WHERE window_attacks >= 3 \
                GROUP BY team \
                ) \
                SELECT team, pressure_sequences \
                FROM pressure \
                WHERE pressure_sequences = (SELECT MAX(pressure_sequences) FROM pressure);",
    "exp": "We first collect all attacking events (shots, crosses, corners) and treat each such event as a potential start of a pressure sequence. For each start event, we count how many attacking events that same team records from the start minute up to two minutes later. If there are at least three attacking events in that window, we treat it as one pressure sequence starting at that event. We then count these sequences per team and select the team(s) with the highest number.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team had the most short bursts of pressure, defined as at least three shots, crosses, or corners within a two-minute window?",
        "Identify the team that generated the highest number of intense attacking flurries over two-minute spans.",
        "Which side produced the most pressure sequences of three or more attacking actions in quick succession?"
    ]
    },
    {
    "id": 61,
    "question": "Which player had the longest continuous 'involvement streak' in the match? A player’s involvement streak is defined as a maximal run of consecutive match minutes in which that player appears in at least one event (of any type) in every minute of the streak, with no gaps of a minute or more without involvement. Find for each player their longest such streak (in minutes) and return the player(s) with the maximum streak length, along with the start and end minutes of that streak.",
    "query": "WITH player_minutes AS ( \
                SELECT DISTINCT player, minute \
                FROM {table_name} \
                WHERE player IS NOT NULL AND player <> '' \
                ), \
                numbered AS ( \
                SELECT \
                    player, \
                    minute, \
                    ROW_NUMBER() OVER (PARTITION BY player ORDER BY minute) AS rn \
                FROM player_minutes \
                ), \
                grouped AS ( \
                SELECT \
                    player, \
                    minute, \
                    minute - rn AS grp \
                FROM numbered \
                ), \
                streaks AS ( \
                SELECT \
                    player, \
                    MIN(minute) AS streak_start_minute, \
                    MAX(minute) AS streak_end_minute, \
                    COUNT(*)    AS streak_length_minutes \
                FROM grouped \
                GROUP BY player, grp \
                ) \
                SELECT \
                player, \
                streak_start_minute, \
                streak_end_minute, \
                streak_length_minutes \
                FROM streaks \
                WHERE streak_length_minutes = (SELECT MAX(streak_length_minutes) FROM streaks);",
    "exp": "We first list all distinct minutes in which each player appears in any event. Using row numbers per player sorted by minute, we transform consecutive minutes into contiguous groups by subtracting the row number from the minute. Identical (minute − row_number) values form a 'run' of consecutive minutes. We then compute the length of each run per player and select the player(s) whose longest involvement streak covers the greatest number of consecutive minutes.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player stayed consistently involved for the longest run of consecutive match minutes?",
        "Find the player whose presence in the event log spans the longest uninterrupted stretch of minutes.",
        "Who has the longest streak of appearing in at least one event every minute without a gap?"
    ]
    },
    {
    "id": 62,
    "question": "Which player created the most 'secondary chances'? A secondary chance is defined as any situation where (1) a player performs an attacking action of type 'shot' or 'cross' for a given team, and (2) the very next attacking event in the match log for that same team is a 'shot', 'cross', or 'goal' by a different teammate, with the second event occurring within at most 1 match minute of the first. Count, for each player, how many secondary chances they created and return the player(s) with the maximum count.",
    "query": "WITH base AS ( \
                SELECT event_id, minute, team, player, event_type \
                FROM {table_name} \
                ), \
                candidate AS ( \
                SELECT \
                    b1.event_id AS base_event_id, \
                    b1.player   AS base_player, \
                    b1.team     AS base_team, \
                    b1.minute   AS base_minute, \
                    (SELECT b2.event_id \
                    FROM {table_name} b2 \
                    WHERE b2.team = b1.team \
                    AND b2.event_type IN ('shot','cross','goal') \
                    AND (b2.minute > b1.minute \
                            OR (b2.minute = b1.minute AND b2.event_id > b1.event_id)) \
                    ORDER BY b2.minute, b2.event_id \
                    LIMIT 1) AS next_team_attack_id \
                FROM base b1 \
                WHERE b1.player IS NOT NULL AND b1.player <> '' \
                    AND b1.team IS NOT NULL AND b1.team <> '' \
                    AND b1.event_type IN ('shot','cross') \
                ), \
                secondary AS ( \
                SELECT \
                    c.base_player AS player, \
                    c.base_team   AS team, \
                    COUNT(*)      AS secondary_chances \
                FROM candidate c \
                JOIN {table_name} n \
                    ON n.event_id = c.next_team_attack_id \
                WHERE n.player IS NOT NULL AND n.player <> '' \
                    AND n.player <> c.base_player \
                    AND n.minute - c.base_minute BETWEEN 0 AND 1 \
                GROUP BY c.base_player, c.base_team \
                ) \
                SELECT player, team, secondary_chances \
                FROM secondary \
                WHERE secondary_chances = (SELECT MAX(secondary_chances) FROM secondary);",
    "exp": "We focus on events where a player takes a shot or makes a cross for their team. For each such event, we look ahead in the log to find the next attacking event (shot, cross, or goal) by the same team. If that next attacking event is by a different player on the same team and occurs within at most 1 minute of the original action, we count it as a secondary chance created by the first player. We then sum these secondary chances per player and select the player(s) with the highest total.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player most often set up a teammate’s follow-up shot, cross, or goal as the next attacking action for their team?",
        "Identify the player whose shots or crosses most frequently led directly to a teammate’s attacking action within a minute.",
        "Who created the largest number of quick follow-up chances for their teammates?"
    ]
    },
    {
    "id": 63,
    "question": "Which defensive player recorded the most 'danger-prevention events'? We define a danger-prevention event as the very next event in the log after an opponent’s attacking action (a 'shot' or 'cross') where (a) the event belongs to the opposing team (the defending team), (b) the event has a non-null player, and (c) the text of the description for that event contains defensive keywords such as 'clear', 'clears', 'clearance', 'block', 'blocks', or 'intercept' (case-insensitive). Count, for each defending player, how many such danger-prevention events they performed and return the player(s) with the maximum count.",
    "query": "WITH ordered AS ( \
                SELECT event_id, minute, team, player, event_type, LOWER(COALESCE(description, '')) AS description_lower \
                FROM {table_name} \
                ), \
                attacking AS ( \
                SELECT o1.event_id, o1.minute, o1.team AS attacking_team \
                FROM ordered o1 \
                WHERE o1.event_type IN ('shot','cross') \
                    AND o1.team IS NOT NULL AND o1.team <> '' \
                ), \
                next_def AS ( \
                SELECT \
                    a.event_id        AS attack_event_id, \
                    a.attacking_team  AS attacking_team, \
                    (SELECT o2.event_id \
                    FROM ordered o2 \
                    WHERE (o2.minute > a.minute \
                            OR (o2.minute = a.minute AND o2.event_id > a.event_id)) \
                    ORDER BY o2.minute, o2.event_id \
                    LIMIT 1) AS next_event_id \
                FROM attacking a \
                ), \
                defended AS ( \
                SELECT \
                    d.player, \
                    d.team, \
                    COUNT(*) AS danger_preventions \
                FROM next_def n \
                JOIN ordered d \
                    ON d.event_id = n.next_event_id \
                WHERE d.team IS NOT NULL AND d.team <> '' \
                    AND d.team <> n.attacking_team \
                    AND d.player IS NOT NULL AND d.player <> '' \
                    AND (d.description_lower LIKE '%clear%' \
                        OR d.description_lower LIKE '%block%' \
                        OR d.description_lower LIKE '%intercept%') \
                GROUP BY d.player, d.team \
                ) \
                SELECT player, team, danger_preventions \
                FROM defended \
                WHERE danger_preventions = (SELECT MAX(danger_preventions) FROM defended);",
    "exp": "We start from all attacking actions (shots and crosses) and, for each, look at the very next event in the match log. If that next event belongs to the other team, names a specific player, and the commentary text includes defensive keywords such as 'clear', 'block', or 'intercept', we treat it as a danger-prevention event by that defender. We then count these danger-prevention events per player and return the defender(s) with the highest count.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player most often appears in the very next event clearing or blocking danger after an opponent’s shot or cross?",
        "Identify the defender who recorded the most clearances, blocks, or interceptions immediately after opposition attacking actions.",
        "Who led the match in directly preventing danger as the immediate response to an opponent’s shot or cross?"
    ]
    },
    {
    "id": 64,
    "question": "Which player most often triggered a 'momentum swing'? We define a momentum swing trigger as any event involving a player whose team is recorded as the next three consecutive events in the match log (i.e., after that player’s event, the following three events all belong to the same team as that player, regardless of event_type). For each player, count how many times their actions were followed by three more consecutive events by their own team, and return the player(s) with the highest such count.",
    "query": "WITH ordered AS ( \
                SELECT \
                    event_id, \
                    minute, \
                    team, \
                    player, \
                    event_type, \
                    ROW_NUMBER() OVER (ORDER BY minute, event_id) AS rn \
                FROM {table_name} \
                WHERE team IS NOT NULL AND team <> '' \
                ), \
                with_leads AS ( \
                SELECT \
                    o.*, \
                    LEAD(team, 1) OVER (ORDER BY rn) AS team1, \
                    LEAD(team, 2) OVER (ORDER BY rn) AS team2, \
                    LEAD(team, 3) OVER (ORDER BY rn) AS team3 \
                FROM ordered o \
                ), \
                swings AS ( \
                SELECT \
                    player, \
                    team, \
                    COUNT(*) AS momentum_triggers \
                FROM with_leads \
                WHERE player IS NOT NULL AND player <> '' \
                    AND team1 = team \
                    AND team2 = team \
                    AND team3 = team \
                GROUP BY player, team \
                ) \
                SELECT player, team, momentum_triggers \
                FROM swings \
                WHERE momentum_triggers = (SELECT MAX(momentum_triggers) FROM swings);",
    "exp": "We impose a strict ordering over all team-tagged events using row numbers. For each event where a player and team are known, we look at the next three events in the log. If all three of those subsequent events belong to the same team as the player’s team, we count that original event as a momentum swing trigger. After counting such triggers per player, we select the player(s) who initiated the most of these four-event momentum runs.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which players actions most often kick-started a sequence where their team controlled the next three events in a row?",
        "Find the player who most frequently began four-event stretches fully dominated by their own team.",
        "Who most often triggered runs of three consecutive follow-up events by their team after their own involvement?"
    ]
    },
    {
    "id": 65,
    "question": "Which player was involved in the highest number of 'transition sequences'? A transition sequence for a team is defined as three consecutive events in the match log where (1) the first event has event_type = 'general_play' for that team, (2) the second event is for the same team and is an attacking action of type 'cross', 'shot', or 'corner', and (3) the third event is for the same team and is a 'shot' or 'goal'. We attribute each such transition sequence to the player recorded in the second (middle) event. Count, for each player, how many transition sequences they are credited with and return the player(s) with the maximum count.",
    "query": "WITH ordered AS ( \
                SELECT \
                    event_id, \
                    minute, \
                    team, \
                    player, \
                    event_type, \
                    ROW_NUMBER() OVER (ORDER BY minute, event_id) AS rn \
                FROM {table_name} \
                WHERE team IS NOT NULL AND team <> '' \
                ), \
                triples AS ( \
                SELECT \
                    mid.player AS player, \
                    mid.team  AS team \
                FROM ordered mid \
                JOIN ordered first \
                    ON first.rn = mid.rn - 1 \
                JOIN ordered third \
                    ON third.rn = mid.rn + 1 \
                WHERE mid.player IS NOT NULL AND mid.player <> '' \
                    AND first.team = mid.team \
                    AND mid.team   = third.team \
                    AND first.event_type = 'general_play' \
                    AND mid.event_type   IN ('cross','shot','corner') \
                    AND third.event_type IN ('shot','goal') \
                ), \
                counts AS ( \
                SELECT \
                    player, \
                    team, \
                    COUNT(*) AS transition_sequences \
                FROM triples \
                GROUP BY player, team \
                ) \
                SELECT player, team, transition_sequences \
                FROM counts \
                WHERE transition_sequences = (SELECT MAX(transition_sequences) FROM counts);",
    "exp": "We order all team-tagged events and look at every triple of consecutive events. For each triple, if all three events belong to the same team, the first is 'general_play', the second is a more explicit attacking action (cross, shot, or corner), and the third is a shot or a goal, we treat that triple as a transition sequence. The middle event’s player is credited with that transition. We then count transition sequences per player and return the player(s) responsible for the most such transitions.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player most often turned general play into an attacking move that soon resulted in a shot or goal?",
        "Identify the player credited with the most three-event sequences: general play → attacking action → shot/goal for the same team.",
        "Who drove the most successful transitions from buildup to final attempt within three consecutive events?"
    ]
    },
    {
    "id": 66,
    "question": "Which substitute had the highest 'impact factor'? For each substitution event where the 'player' column is the player coming onto the pitch for a given team at a certain minute, we define that player’s impact factor as: (A) the total number of attacking events ('shot', 'cross', or 'goal') by that player’s team from that substitution minute onward, divided by (B) the total number of events (of any event_type) by that same team before the substitution minute. Only consider substitutions where the team had at least one event before the substitution. Compute this impact factor for each substitute and return the substitute(s) with the highest impact factor, also showing their pre-substitution team events and post-substitution attacking events.",
    "query": "WITH subs AS ( \
                SELECT event_id, minute, team, player \
                FROM {table_name} \
                WHERE event_type = 'substitution' \
                    AND player IS NOT NULL AND player <> '' \
                    AND team IS NOT NULL AND team <> '' \
                ), \
                sub_impacts AS ( \
                SELECT \
                    s.player, \
                    s.team, \
                    s.minute, \
                    (SELECT COUNT(*) \
                    FROM {table_name} t \
                    WHERE t.team = s.team \
                    AND t.minute < s.minute) AS pre_team_events, \
                    (SELECT COUNT(*) \
                    FROM {table_name} t \
                    WHERE t.team = s.team \
                    AND t.minute >= s.minute \
                    AND t.event_type IN ('shot','cross','goal')) AS post_attacking_events \
                FROM subs s \
                ), \
                with_ratio AS ( \
                SELECT \
                    player, \
                    team, \
                    minute AS substitution_minute, \
                    pre_team_events, \
                    post_attacking_events, \
                    CASE WHEN pre_team_events > 0 \
                        THEN CAST(post_attacking_events AS FLOAT) / pre_team_events \
                        ELSE NULL \
                    END AS impact_factor \
                FROM sub_impacts \
                WHERE pre_team_events > 0 \
                ) \
                SELECT \
                player, \
                team, \
                substitution_minute, \
                impact_factor, \
                pre_team_events, \
                post_attacking_events \
                FROM with_ratio \
                WHERE impact_factor = (SELECT MAX(impact_factor) FROM with_ratio);",
    "exp": "We treat each substitution event as the moment a new player enters for a team. For that team, we count how many events occurred before the substitution (the baseline) and how many attacking events (shots, crosses, goals) occurred from that substitution minute onward. The impact factor is defined as post-substitution attacking events divided by pre-substitution total events, only for cases where there was at least one pre-substitution event. We calculate this ratio for every substitute and return the one(s) with the highest impact factor.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which substitute had the biggest attacking impact relative to how active their team had been before they came on?",
        "Identify the player who came on and was followed by the most attacking actions per prior team event.",
        "Who was the most high-impact substitute when comparing post-substitution attacking volume to pre-substitution overall activity?"
    ]
    },
    {
    "id": 67,
    "question": "Which player initiated the most 'successful attacking sequences'? A successful attacking sequence is defined as starting from an event for a team with event_type in ('general_play', 'cross', 'free_kick', 'corner') and, within the next 5 events in the global event order, there exists at least one event for the same team with event_type 'shot' or 'goal'. We attribute the sequence to the player recorded in the starting event, and we count each start that leads to at least one such shot/goal as one successful sequence (even if multiple shots/goals follow within those five events). For each player, count how many successful attacking sequences they initiated and return the player(s) with the maximum count.",
    "query": "WITH ordered AS ( \
                SELECT \
                    event_id, \
                    minute, \
                    team, \
                    player, \
                    event_type, \
                    ROW_NUMBER() OVER (ORDER BY minute, event_id) AS rn \
                FROM {table_name} \
                WHERE team IS NOT NULL AND team <> '' \
                ), \
                starts AS ( \
                SELECT * \
                FROM ordered \
                WHERE event_type IN ('general_play','cross','free_kick','corner') \
                    AND player IS NOT NULL AND player <> '' \
                ), \
                future AS ( \
                SELECT \
                    s.player, \
                    s.team, \
                    s.rn AS start_rn, \
                    EXISTS ( \
                    SELECT 1 \
                    FROM ordered o2 \
                    WHERE o2.team = s.team \
                        AND o2.rn > s.rn \
                        AND o2.rn <= s.rn + 5 \
                        AND o2.event_type IN ('shot','goal') \
                    ) AS has_shot_or_goal \
                FROM starts s \
                ), \
                sequences AS ( \
                SELECT \
                    player, \
                    team, \
                    COUNT(*) AS successful_sequences \
                FROM future \
                WHERE has_shot_or_goal \
                GROUP BY player, team \
                ) \
                SELECT player, team, successful_sequences \
                FROM sequences \
                WHERE successful_sequences = (SELECT MAX(successful_sequences) FROM sequences);",
    "exp": "We order all team-tagged events and mark as potential sequence starts any event of type 'general_play', 'cross', 'free_kick', or 'corner' with a known player. For each start, we look ahead to the next five events in the global order and check if, for the same team, there is at least one 'shot' or 'goal'. If so, that starting player is credited with one successful attacking sequence. We then count such sequences per player and return the player(s) who initiated the most.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which player most frequently started moves that ended in a shot or goal within the next few events for their team?",
        "Identify the player who initiated the greatest number of short attacking sequences culminating in a shot or goal.",
        "Who most often began passages of play (over the next five events) that produced a shot or goal for their side?"
    ]
    },
    {
    "id": 68,
    "question": "Which team had the highest 'red zone occupation ratio'? We define a team’s red zone occupation as the proportion of its attacking events that are explicitly described as being in or near the penalty box. For each team, we count: (A) all attacking events with event_type in ('shot', 'cross', 'corner', 'penalty', 'goal'), and (B) among those, the subset where the description text (case-insensitive) contains the word 'box' (e.g., 'penalty box', 'into the box'). The red zone occupation ratio is B divided by A. Return the team(s) with the highest ratio, as well as their total attacking events and red-zone events.",
    "query": "WITH team_events AS ( \
                SELECT \
                    team, \
                    SUM(CASE WHEN event_type IN ('shot','cross','corner','penalty','goal') THEN 1 ELSE 0 END) AS total_attacking_events, \
                    SUM(CASE WHEN event_type IN ('shot','cross','corner','penalty','goal') \
                            AND LOWER(COALESCE(description, '')) LIKE '%box%' \
                            THEN 1 ELSE 0 END) AS red_zone_events \
                FROM {table_name} \
                WHERE team IS NOT NULL AND team <> '' \
                GROUP BY team \
                ), \
                with_ratio AS ( \
                SELECT \
                    team, \
                    total_attacking_events, \
                    red_zone_events, \
                    CASE WHEN total_attacking_events > 0 \
                        THEN CAST(red_zone_events AS FLOAT) / total_attacking_events \
                        ELSE 0 \
                    END AS red_zone_ratio \
                FROM team_events \
                ) \
                SELECT \
                team, \
                total_attacking_events, \
                red_zone_events, \
                red_zone_ratio \
                FROM with_ratio \
                WHERE red_zone_ratio = (SELECT MAX(red_zone_ratio) FROM with_ratio);",
    "exp": "We aggregate per team all attacking events (shots, crosses, corners, penalties, and goals) and simultaneously count how many of these mention the term 'box' in the description, indicating action in or near the penalty area. The red zone occupation ratio is the share of attacking events that explicitly occur 'in the box'. We compute this ratio for every team and return the team(s) with the highest value, along with the underlying counts.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which team spent the largest share of its attacking actions in or near the penalty box, according to the commentary?",
        "Identify the side whose attacking events most frequently reference the penalty box in their descriptions.",
        "Who had the highest proportion of attacks described as happening 'in the box'?"
    ]
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
}





]