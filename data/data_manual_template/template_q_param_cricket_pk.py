## to do : hattrick of wickets, sixes, wides, count of no balls, runs scored after no balls, extra runs in wides or no balls## top n, 
question_templates = [
    {
    "id": 1,
    "question": "Find the bowler who has given the most runs and how many runs has the bowler given?",
    "query": "SELECT bowler, SUM(bowler_runs_given) AS total_runs_bowler              FROM {table_name}              GROUP BY bowler              HAVING SUM(bowler_runs_given) = (                  SELECT MAX(total_runs_bowler)                  FROM (                      SELECT SUM(bowler_runs_given) AS total_runs_bowler                      FROM {table_name}                      GROUP BY bowler                  ) AS sub              );",
    "exp": "Get all bowler rows and groups by bowler. Calculate sum for runs given and orders descending order",
    "variables": ["table_name"],
    "paraphrases": [
        "Which bowler allowed the most runs, and what was that total?",
        "Who was the most expensive bowler in terms of runs conceded, and what was their run count?",
        "Could you identify the bowler who gave up the highest number of runs, along with the exact amount?"
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 2,
    "question": "Which batsman has faced the most balls and how many balls has the batsman faced?",
    "query": "SELECT              batsman,              SUM(batsman_bowls_faced) AS total_balls_batsman            FROM {table_name}            GROUP BY batsman            HAVING SUM(batsman_bowls_faced) = (              SELECT MAX(total_balls_batsman)              FROM (                SELECT SUM(batsman_bowls_faced) AS total_balls_batsman                FROM {table_name}                GROUP BY batsman              ) AS x            );",
    "exp": "Get all rows grouped by batsman. Sum the balls faced by each batsman, sort in descending order of total balls, and return the top result.",
    "variables": ["table_name"],
    "paraphrases": [
        "Who is the batsman who faced the most deliveries, and what's the total number of balls they faced?",
        "Can you tell me which batsman played the most balls, and how many that was?",
        "Identify the batsman with the highest number of balls faced, and state that number."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 3,
    "question": "In which over did {batsman} hit their first four and who was the bowler?",
    "query": "SELECT Ceil(overs) as over_number, bowler FROM {table_name} WHERE batsman = '{batsman}' AND batsman_runs = 4 ORDER BY overs ASC LIMIT 1;",
    "exp": "Find all deliveries where the given batsman hit a four, sort them by over in ascending order, and return the earliest one along with the bowler.",
    "variables": ["table_name", "batsman"],
    "paraphrases": [
        "When did {batsman} score their initial four, and which bowler delivered that ball?",
        "Could you pinpoint the over in which {batsman} hit their very first boundary of four runs, and who was bowling at that moment?",
        "For {batsman}, what over saw their first four, and who was the bowler on that occasion?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 4,
    "question": "How many fours did {batsman} hit against {bowler}? Show the tally in table.",
    "query": "SELECT COUNT(*) AS total_fours_batsman_vs_bowler FROM {table_name} WHERE batsman = '{batsman}' AND bowler = '{bowler}' AND batsman_runs = 4;",
    "exp": "Count how many times the given batsman hit a four against the given bowler.",
    "variables": ["table_name", "batsman", "bowler"],
    "paraphrases": [
        "Please provide a table showing the number of fours {batsman} scored off {bowler}.",
        "Can you give me a breakdown of how many boundaries of four runs {batsman} hit specifically against {bowler}?",
        "List the count of fours hit by {batsman} when facing {bowler}, presented in a table format."
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 5,
    "question": "What is the total number of wickets taken by {bowler1} and {bowler2} combined?",
    "query": "SELECT SUM(bowler_wickets) AS total_wickets_bowler FROM {table_name} WHERE bowler IN ('{bowler1}', '{bowler2}');",
    "exp": "Sum up the total wickets taken by the two specified bowlers across all deliveries.",
    "variables": ["table_name", "bowler1", "bowler2"],
    "paraphrases": [
        "How many wickets did {bowler1} and {bowler2} take together?",
        "What's the combined wicket count for {bowler1} and {bowler2}?",
        "Could you provide the total number of wickets claimed by both {bowler1} and {bowler2} collectively?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 6,
    "question": "Who bowled the most number of balls and how many balls has that bowler bowled?",
    "query": "SELECT              bowler,              SUM(bowler_bowls_done) AS total_bowls_bowler            FROM {table_name}            GROUP BY bowler            HAVING SUM(bowler_bowls_done) = (              SELECT MAX(total_bowls_bowler)              FROM (                SELECT SUM(bowler_bowls_done) AS total_bowls_bowler                FROM {table_name}                GROUP BY bowler              ) AS x            );",
    "exp": "Group all rows by bowler, sum the number of balls bowled by each, sort in descending order, and return the bowler who bowled the most balls.",
    "variables": ["table_name"],
    "paraphrases": [
        "Which bowler delivered the most balls, and what was their total ball count?",
        "Identify the bowler who bowled the highest number of deliveries, along with that specific number.",
        "Can you tell me who bowled the most balls in the match, and how many deliveries they sent down?"
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 7,
    "question": "How many runs did {batsman} score?",
    "query": "SELECT SUM(batsman_runs) AS total_runs_batsman FROM {table_name} WHERE batsman = '{batsman}';",
    "exp": "Calculate the total runs scored by the specified batsman across all deliveries.",
    "variables": ["table_name", "batsman"],
    "paraphrases": [
        "What was {batsman}'s total score?",
        "How many runs did {batsman} manage to get?",
        "Could you tell me the total runs scored by {batsman}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 8,
    "question": "What is the average number of runs given by {bowler}?",
    "query": "SELECT AVG(bowler_runs_given) AS avg_runs_given_bowler FROM {table_name} WHERE bowler = '{bowler}';",
    "exp": "Calculate the average runs conceded per delivery by the specified bowler.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "What's the average runs conceded by {bowler}?",
        "Can you tell me {bowler}'s average runs given away?",
        "Calculate the average runs {bowler} allowed per over."
    ],
    "primary_key": ["N/A"]
    },
    # {
    #   "id": 9,
    #   "question": "Which batsman faced the most balls and how many balls did they face?",
    #   "query": "SELECT batsman, SUM(batsman_bowls_faced) AS total_bowls_faced FROM {table_name} GROUP BY batsman ORDER BY total_bowls_faced DESC LIMIT 1;",
    #   "exp": "Group all rows by batsman, sum the balls faced by each batsman, sort them in descending order, and return the batsman who faced the most balls.",
    #   "variables": ["table_name"],
    #   "paraphrases": [
    #     "Who faced the most deliveries among all batsmen, and what was their ball count played by them?",
    #     "Identify the batsman who played the highest number of balls, and state the exact figure.",
    #     "Which batsman had the most balls come their way, and how many deliveries was that?"
    #   ]
    # },
    {
    "id": 10,
    "question": "How many wickets were taken in total combined by every bowler?",
    "query": "SELECT SUM(bowler_wickets) AS total_wickets_bowler FROM {table_name};",
    "exp": "Calculate the total number of wickets taken by all bowlers combined across the entire match.",
    "variables": ["table_name"],
    "paraphrases": [
        "What's the grand total of wickets taken by all bowlers in the match?",
        "Could you tell me the combined number of wickets claimed by every bowler?",
        "How many wickets fell in total across all bowlers?"
    ],
    "primary_key": ["N/A"]
    },
    # {
    #   "id": 11,
    #   "question": "Which bowler took the most wickets and gave the fewest runs among wicket taking bowlers?",
    #   "query": "SELECT\
    #           bowler,\
    #           SUM(bowler_wickets) AS total_wickets_bowler,\
    #           SUM(bowler_runs_given) AS total_runs_given_bowler\
    #         FROM {table_name}\
    #         GROUP BY bowler\
    #         HAVING\
    #           -- only wicket-taking bowlers\
    #           SUM(bowler_wickets) > 0\
    #           -- among all bowlers, keep only those with the max wickets\
    #           AND SUM(bowler_wickets) = (\
    #             SELECT MAX(wkts)\
    #             FROM (\
    #               SELECT SUM(bowler_wickets) AS wkts\
    #               FROM {table_name}\
    #               GROUP BY bowler\
    #             ) m\
    #           )\
    #           -- and among that max-wicket set, keep only the fewest runs\
    #           AND SUM(bowler_runs_given) = (\
    #             SELECT MIN(runs)\
    #             FROM (\
    #               SELECT\
    #                 SUM(bowler_runs_given) AS runs\
    #               FROM {table_name}\
    #               GROUP BY bowler\
    #               HAVING SUM(bowler_wickets) = (\
    #                 SELECT MAX(wkts)\
    #                 FROM (\
    #                   SELECT SUM(bowler_wickets) AS wkts\
    #                   FROM {table_name}\
    #                   GROUP BY bowler\
    #                 ) mm\
    #               )\
    #             ) r\
    #           );",
    #   "exp": "Group all rows by bowler having wickets >1, sum the wickets taken and runs conceded by each, then return the bowler with the most wickets and fewest runs conceded.",
    #   "variables": ["table_name"],
    #   "paraphrases": [
    #     "Identify the bowler who was both the most successful in taking wickets and the most economical in terms of runs among wicket taking bowlers.",
    #     "Who is the bowler that took the most wickets while also conceding the least runs among wicket taking bowlers?",
    #     "Which bowler had the best combination of taking the most wickets and giving away the fewest runs?"
    #   ]
    # },
    {
    "id": 12,
    "question": "Calculate the total number of fours hit by batsmen against {bowler}.",
    "query": "SELECT SUM(batsman_fours) AS total_fours_bowler FROM {table_name} WHERE bowler = '{bowler}';",
    "exp": "Calculate the total number of fours hit by all batsmen against the specified bowler.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "How many fours in total did batsmen hit when facing {bowler}?",
        "Can you sum up all the fours scored against {bowler} by various batsmen?",
        "What's the cumulative count of fours hit off {bowler}'s bowling?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 13,
    "question": "Calculate the total number of sixes hit by batsmen against {bowler}.",
    "query": "SELECT SUM(batsman_sixes) AS total_sixes_bowler FROM {table_name} WHERE bowler = '{bowler}';",
    "exp": "Calculate the total number of sixes hit by all batsmen against the specified bowler.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "What's the total number of sixes batsmen scored against {bowler}?",
        "How many maximums (sixes) were hit off {bowler}'s bowling in total?",
        "Can you tell me the combined count of sixes hit by batsmen when facing {bowler}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 14,
    "question": "Calculate the total number of dots hit by {batsman} against {bowler}.",
    "query": "SELECT COUNT(*) AS total_dots FROM {table_name} WHERE batsman = '{batsman}' AND bowler = '{bowler}' AND team_runs = 0;",
    "exp": "Count the number of dot balls (deliveries with zero runs) bowled by the specified bowler to the specified batsman.",
    "variables": ["table_name", "batsman", "bowler"],
    "paraphrases": [
        "How many dot balls did {batsman} play when facing {bowler}?",
        "Can you count the number of deliveries {bowler} bowled to {batsman} that yielded no runs?",
        "What's the total count of dot balls faced by {batsman} from {bowler}?"
    ],
    "primary_key": ["N/A"]
    },
    # {
    #   "id": 15,
    #   "question": "Find the batsman who scored the most runs against {bowler} and also hit the most sixes.",
    #   "query": "SELECT batsman, SUM(batsman_runs) AS total_runs, SUM(batsman_sixes) AS total_sixes FROM {table_name} WHERE bowler = '{bowler}' GROUP BY batsman ORDER BY total_runs DESC, total_sixes DESC LIMIT 1;",
    #   "exp": "Group deliveries by batsman for a specific bowler, sum their runs and sixes, then return the batsman who scored the most runs and sixes against that bowler.",
    #   "variables": ["table_name", "bowler"],
    #   "paraphrases": [
    #     "Identify the batsman who not only scored the most runs but also hit the most sixes specifically against {bowler}.",
    #     "Which batsman dominated {bowler} by scoring the highest runs and hitting the most sixes?",
    #     "Who was the top scorer and top six-hitter against {bowler}?"
    #   ]
    # },
    {
    "id": 16,
    "question": "What is the total number of runs scored by batsmen combined who faced 10 or more balls and hit 2 or more fours?",
    "query": "SELECT SUM(total_runs) AS total_runs_batsman FROM ( SELECT batsman, SUM(batsman_runs) AS total_runs, SUM(batsman_bowls_faced) AS total_balls, SUM(batsman_fours) AS total_fours FROM {table_name} GROUP BY batsman HAVING SUM(batsman_bowls_faced) >= 10 AND SUM(batsman_fours) >= 2)",
    "exp": "Find batsmen who faced at least 10 balls and hit at least 2 fours, then sum the total runs scored by these batsmen.",
    "variables": ["table_name"],
    "paraphrases": [
        "For batsmen who faced at least 10 balls and hit 2 or more fours, what's their total run count?",
        "Calculate the combined runs of all batsmen who met the criteria of facing 10+ balls and hitting 2+ fours.",
        "Among batsmen who faced at least 10 deliveries and struck two or more fours, what's their aggregate score?"
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 18,
    "question": "Find the bowler who conceded the most runs in the entire match and the batsman who scored the most runs against him in a single over. How many runs did the batsman score overall in the match and how many runs did batsman score against him in single over ?",
    "query": "WITH bowler_totals AS (              SELECT                bowler,                SUM(bowler_runs_given) AS total_runs_conceded              FROM {table_name}              GROUP BY bowler            ),            top_bowlers AS (              SELECT bt.bowler              FROM bowler_totals bt              WHERE bt.total_runs_conceded = (                SELECT MAX(total_runs_conceded) FROM bowler_totals              )            ),            batsman_over AS (              SELECT                t.bowler,                (CAST(t.overs AS INTEGER) + CASE WHEN t.overs > CAST(t.overs AS INTEGER) THEN 1 ELSE 0 END) AS over_number,                t.batsman,                SUM(t.batsman_runs) AS runs_in_over              FROM {table_name} t              WHERE t.bowler IN (SELECT bowler FROM top_bowlers)              GROUP BY                t.bowler,                (CAST(t.overs AS INTEGER) + CASE WHEN t.overs > CAST(t.overs AS INTEGER) THEN 1 ELSE 0 END),                t.batsman            ),            top_batsman_over AS (              SELECT bo.*              FROM batsman_over bo              JOIN (                SELECT bowler, MAX(runs_in_over) AS max_runs_in_over                FROM batsman_over                GROUP BY bowler              ) m                ON m.bowler = bo.bowler              AND m.max_runs_in_over = bo.runs_in_over            ),            batsman_totals AS (              SELECT batsman, SUM(batsman_runs) AS total_batsman_runs_in_match              FROM {table_name}              GROUP BY batsman            )            SELECT              tbo.bowler,              tbo.over_number,              tbo.batsman,              tbo.runs_in_over AS batsman_runs_in_over,              bt.total_batsman_runs_in_match            FROM top_batsman_over tbo            JOIN batsman_totals bt              ON bt.batsman = tbo.batsman            ORDER BY tbo.bowler, tbo.batsman, tbo.over_number;",
    "exp": "First, find the bowler who conceded the most runs in the match. Then among that bowler's overs, find the batsman who scored the most runs in a single over (grouped by Ceil(overs)) against the bowler. Finally, get that batsman's total runs in the match.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the bowler who gave away the most runs in a single over, and specify which batsman scored the most against him in that particular over, along with the runs scored by that batsman.",
        "Which bowler had the most expensive over, and who was the batsman who capitalized most on it, scoring how many runs in that one over?",
        "Locate the bowler with the highest runs conceded in an over, and then tell me which batsman was responsible for most of those runs, and their individual contribution in that over."
    ],
    "primary_key": ["bowler", "batsman", "over_number"] 
    },
    {
    "id": 19,
    "question": "How many times did each batsman face the bowler {bowler} including the extras?",
    "query": "SELECT batsman, COUNT(*) AS interactions FROM {table_name} WHERE bowler = '{bowler}' GROUP BY batsman;",
    "exp": "Get all rows where the bowler is present, group them by batsman, and count how many times each batsman appeared — including all deliveries (legal and extras) bowled by that bowler.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "For each batsman, how many deliveries did they face from {bowler}?",
        "Count the number of times each batsman had to bat against {bowler}.",
        "Provide a tally of how many balls each batsman received from {bowler}."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 20,
    "question": "Calculate the total runs scored by each batsman who hit a six or a four.",
    "query": "SELECT batsman, SUM(batsman_runs) AS total_runs_batsman FROM {table_name} WHERE batsman_sixes > 0 OR batsman_fours > 0 GROUP BY batsman;",
    "exp": "Get rows where batsman hit at least one four or six, group them by batsman, and calculate total runs scored by each.",
    "variables": ["table_name"],
    "paraphrases": [
        "Show the total runs for batsmen who hit at least one boundary (four or six).",
        "For each batsman who scored a four or a six, what was their overall run total?",
        "List the total runs scored by batsmen, but only include those who managed to hit either a four or a six."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 21,
    "question": "Which bowler gave the most runs in an over and what was the over number?",
    "query": "SELECT              bowler,              CEIL(overs) AS over_number,              SUM(bowler_runs_given) AS runs_in_over_bowler            FROM {table_name}            GROUP BY bowler, CEIL(overs)            HAVING SUM(bowler_runs_given) = (              SELECT MAX(runs_in_over_bowler)              FROM (                SELECT                  bowler,                  CEIL(overs) AS over_number,                  SUM(bowler_runs_given) AS runs_in_over_bowler                FROM {table_name}                GROUP BY bowler, CEIL(overs)              ) s            );",
    "exp": "Group data by each over and bowler, calculate total runs given by each bowler in each over, then find the over where a bowler conceded the most runs.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the bowler who conceded the most runs in a single over, and tell me which over it was.",
        "Which over was the most expensive in terms of runs given away, and who was the bowler?",
        "Find the over with the highest run count for a bowler, and specify the bowler and over number."
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 22,
    "question": "Find the bowler who conceded the fewest runs while taking at least one wicket.",
    "query": "SELECT              bowler,              SUM(bowler_runs_given) AS total_runs_bowler            FROM {table_name}            GROUP BY bowler            HAVING              SUM(bowler_wickets) > 0              AND SUM(bowler_runs_given) = (                SELECT MIN(runs)                FROM (                  SELECT SUM(bowler_runs_given) AS runs                  FROM {table_name}                  GROUP BY bowler                  HAVING SUM(bowler_wickets) > 0                ) t              );",
    "exp": "Group data by bowler, keep only bowlers who took at least one wicket, then find the one who gave the least total runs.",
    "variables": ["table_name"],
    "paraphrases": [
        "Among bowlers who took at least one wicket, who was the most economical (conceded the fewest runs)?",
        "Identify the bowler with the lowest run concession who also managed to take at least one wicket.",
        "Which bowler gave away the least runs while still picking up at least one wicket?"
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 23,
    "question": "Name the batsmen who hit at least one six and what is the total runs scored by them?",
    "query": "SELECT              batsman,              SUM(batsman_runs)  AS total_runs_batsman,              SUM(batsman_sixes) AS total_sixes_batsman            FROM {table_name}            GROUP BY batsman            HAVING SUM(batsman_sixes) > 0;",
    "exp": "Filter deliveries where batsman hit at least one six, group by batsman, and calculate total runs scored by each.",
    "variables": ["table_name"],
    "paraphrases": [
        "List the batsmen who hit at least one six, along with their total runs scored.",
        "For batsmen who hit one or more sixes, what are their names and their respective total scores?",
        "Which batsmen scored at least one six, and what was their overall run contribution?"
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 24,
    "question": "What is the total number of runs scored {temporal_phrase} of the match?",
    "query": "SELECT SUM(team_runs) AS total_runs FROM {table_name} WHERE {temporal_predicate};",
    "exp": "Filter deliveries between overs {x1} and {x2}, and calculate the total team runs scored in that range.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many runs were scored in total during {temporal_phrase}?",
        "Calculate the aggregate runs scored from {temporal_phrase}.",
        "What's the cumulative score during the period of the match from {temporal_phrase}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 25,
    "question": "Find the bowler who has given the most runs in the entire match and how many runs has the bowler given {temporal_phrase}?",
    "query": "WITH top_bowler AS ( SELECT bowler, SUM(bowler_runs_given) AS total_runs FROM {table_name} GROUP BY bowler ORDER BY total_runs DESC LIMIT 1 ), runs_in_range AS ( SELECT SUM(bowler_runs_given) AS runs_in_range FROM {table_name} WHERE bowler = (SELECT bowler FROM top_bowler) AND {temporal_predicate} ) SELECT (SELECT bowler FROM top_bowler) AS bowler, (SELECT total_runs FROM top_bowler) AS total_runs_given, (SELECT runs_in_range FROM runs_in_range) AS runs_given_in_range;",
    "exp": "Find the bowler who gave the most runs overall, then calculate how many of those runs came in the overs between {x1} and {x2}.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Which bowler conceded the most runs between {temporal_phrase}, and what was that amount?",
        "In the {temporal_phrase}, who was the most expensive bowler, and how many runs did they give away?",
        "Identify the bowler who leaked the most runs during {temporal_phrase}, and state their run tally."
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 26,
    "question": "Which batsman has faced the most balls in the entire match and how many balls has the batsman faced {temporal_phrase}?",
    "query": "SELECT              batsman,              SUM(batsman_bowls_faced) AS total_balls_faced,              SUM(CASE WHEN {temporal_predicate}                      THEN batsman_bowls_faced ELSE 0 END) AS balls_faced_between_overs            FROM {table_name}            GROUP BY batsman            HAVING              SUM(batsman_bowls_faced) = (                SELECT MAX(total_balls)                FROM (                  SELECT SUM(batsman_bowls_faced) AS total_balls                  FROM {table_name}                  GROUP BY batsman                ) t              );",
    "exp": "Find the batsman who faced the most balls overall, then calculate how many balls that batsman faced between overs {x1} and {x2}.",
    "variables": ["table_name", "temporal_phrase","temporal_predicate"],
    "paraphrases": [
        "{temporal_phrase}, which batsman faced the highest number of deliveries, and what was that count?",
        "During the period of play from {temporal_phrase}, who was the batsman who faced the most balls, and how many?",
        "Identify the batsman who faced the most balls {temporal_phrase}, and state the total deliveries."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 27,
    "question": "In which over did {batsman} hit his first four {temporal_phrase}?",
    "query": "SELECT overs as over_number FROM {table_name} WHERE batsman = '{batsman}' AND batsman_runs = 4 AND {temporal_predicate} ORDER BY over_number ASC LIMIT 1;",
    "exp": "Find the earliest over between {x1} and {x2} where the batsman hit a four.",
    "variables": ["table_name", "batsman", "temporal_phrase","temporal_predicate"],
    "paraphrases": [
        "{temporal_phrase}, in which over did {batsman} hit their inaugural four?",
        "For {batsman}, when did their first four occur {temporal_phrase}?",
        "Can you tell me the specific over, {temporal_phrase}, where {batsman} scored their initial boundary of four runs?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 28,
    "question": "How many fours did {batsman} hit against {bowler} {temporal_phrase}? Show the tally in table.",
    "query": "SELECT COUNT(*) AS total_fours_batsman FROM {table_name} WHERE batsman = '{batsman}' AND bowler = '{bowler}' AND batsman_runs = 4 AND {temporal_predicate};",
    "exp": "Count the number of deliveries where the batsman scored 4 runs against the bowler {temporal_predicate}.",
    "variables": ["table_name", "batsman", "bowler", "temporal_phrase","temporal_predicate"],
    "paraphrases": [
        "Please provide a table showing how many fours {batsman} hit off {bowler} specifically {temporal_phrase}.",
        "Show me a breakdown of fours hit by {batsman} against {bowler} during {temporal_phrase}.",
        "What's the count of fours scored by {batsman} off {bowler} {temporal_phrase}, presented in a table?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 29,
    "question": "What is the total number of wickets taken by {bowler1} and {bowler2} combined {temporal_phrase}?",
    "query": "SELECT SUM(bowler_wickets) AS total_wickets_bowler FROM {table_name} WHERE bowler IN ('{bowler1}', '{bowler2}') AND {temporal_predicate};",
    "exp": "Get all deliveries bowled by either {bowler1} or {bowler2} {temporal_predicate}, and sum the total wickets taken.",
    "variables": ["table_name", "bowler1", "bowler2", "temporal_phrase","temporal_predicate"],
    "paraphrases": [
        "{temporal_phrase}, how many wickets did {bowler1} and {bowler2} take together?",
        "What's the combined wicket count for {bowler1} and {bowler2} during {temporal_phrase}?",
        "Could you provide the total wickets claimed by both {bowler1} and {bowler2} {temporal_phrase}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 30,
    "question": "Who bowled the most overs in the entire match and in how many overs has that bowler bowled {temporal_phrase}?",
    "query": "SELECT              bowler,              COUNT(DISTINCT CEIL(overs)) AS total_overs_in_match,              COUNT(DISTINCT CASE WHEN {temporal_predicate}                                  THEN CEIL(overs) END) AS overs_in_range            FROM {table_name}            GROUP BY bowler            HAVING COUNT(DISTINCT CEIL(overs)) = (              SELECT MAX(total_overs)              FROM (                SELECT COUNT(DISTINCT CEIL(overs)) AS total_overs                FROM {table_name}                GROUP BY bowler              ) t            );",
    "exp": "Find the bowler who bowled in the most overs across the match, and count how many of those overs were {temporal_predicate}.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate","ceil"],
    "paraphrases": [
        "{temporal_phrase}, which bowler bowled the most overs, and what was their total over count?",
        "Identify the bowler who delivered the highest number of {temporal_phrase}, and state that specific number.",
        "{temporal_phrase}, who bowled the most overs, and how many did they bowl?"
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 31,
    "question": "How many runs did {batsman} score {temporal_phrase}?",
    "query": "SELECT SUM(batsman_runs) AS total_runs_batsman FROM {table_name} WHERE batsman = '{batsman}' AND {temporal_predicate};",
    "exp": "Calculate the total runs scored by the specified batsman between overs {x1} and {x2}.",
    "variables": ["table_name", "batsman", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What was {batsman}'s total score during {temporal_phrase}?",
        "How many runs did {batsman} manage to get {temporal_phrase}?",
        "Could you tell me the total runs scored by {batsman} {temporal_phrase}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 32,
    "question": "What is the average number of runs given by {bowler} {temporal_phrase}?",
    "query": "SELECT AVG(bowler_runs_given) AS avg_runs_given_bowler FROM {table_name} WHERE bowler = '{bowler}' AND {temporal_predicate};",
    "exp": "Calculate the average runs given per delivery by the specified bowler {temporal_predicate}.",
    "variables": ["table_name", "bowler", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What's the average runs conceded by {bowler} during {temporal_phrase}?",
        "Can you tell me {bowler}'s average runs given away {temporal_phrase}?",
        "Calculate the average runs {bowler} allowed per over {temporal_phrase}."
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 34,
    "question": "How many wickets were taken in total combined by every bowler {temporal_phrase}?",
    "query": "SELECT SUM(bowler_wickets) AS total_wickets_bowler FROM {table_name} WHERE {temporal_predicate};",
    "exp": "Calculate the total number of wickets taken by all bowlers combined {temporal_predicate}.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What's the grand total of wickets taken by all bowlers in the match {temporal_phrase}?",
        "Could you tell me the combined number of wickets claimed by every bowler from {temporal_phrase}?",
        "How many wickets fell in total across all bowlers during {temporal_phrase}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 35,
    "question": "Which bowler took the most wickets and gave the fewest runs among wicket taking bowlers {temporal_phrase} and how many runs and wickets were they?",
    "query": "SELECT bowler, SUM(bowler_wickets) AS total_wickets, SUM(bowler_runs_given) AS total_runs FROM {table_name} WHERE {temporal_predicate} GROUP BY bowler ORDER BY total_wickets DESC, total_runs ASC LIMIT 1;",
    "exp": "Find the bowler with the most wickets {temporal_predicate}, breaking ties by fewest runs conceded.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "{temporal_phrase}, identify the bowler who was both the most successful in taking wickets and the most economical in terms of runs, and provide their wicket and run count.",
        "In the {temporal_phrase}, which bowler took the most wickets while conceding the fewest runs, and what were their figures?",
        "Find the bowler with the best combination of wickets and economy rate {temporal_phrase}, and state their runs conceded and wickets taken."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 36,
    "question": "Calculate the total number of fours hit by batsmen against {bowler} between {temporal_phrase}",
    "query": "SELECT SUM(batsman_fours) AS total_fours FROM {table_name} WHERE bowler = '{bowler}' AND {temporal_predicate};",
    "exp": "Calculate the total number of fours hit by all batsmen against the specified bowler {temporal_predicate}.",
    "variables": ["table_name", "bowler", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many fours in total did batsmen hit when facing {bowler} during {temporal_phrase}?",
        "Can you sum up all the fours scored against {bowler} by various batsmen {temporal_phrase}?",
        "What's the cumulative count of fours hit off {bowler}'s bowling in the {temporal_phrase}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 37,
    "question": "Calculate the total number of sixes hit by batsmen against {bowler} {temporal_phrase}",
    "query": "SELECT SUM(batsman_sixes) AS total_sixes FROM {table_name} WHERE bowler = '{bowler}' AND {temporal_predicate};",
    "exp": "Calculate the total number of sixes hit by all batsmen against the specified bowler {temporal_predicate}.",
    "variables": ["table_name", "bowler", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What's the total number of sixes batsmen scored against {bowler} during {temporal_phrase}?",
        "How many maximums (sixes) were hit off {bowler}'s bowling in total {temporal_phrase}?",
        "Can you tell me the combined count of sixes hit by batsmen when facing {bowler} from {temporal_phrase}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 38,
    "question": "Calculate the total number of dots hit by {batsman} against {bowler} {temporal_phrase}",
    "query": "SELECT COUNT(*) AS total_dots FROM {table_name} WHERE batsman = '{batsman}' AND bowler = '{bowler}' AND team_runs = 0 AND {temporal_predicate};",
    "exp": "Count the number of dot balls (no runs scored) delivered by {bowler} to {batsman} {temporal_predicate}.",
    "variables": ["table_name", "batsman", "bowler", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many dot balls did {batsman} play when facing {bowler} {temporal_phrase}?",
        "Can you count the number of deliveries {bowler} bowled to {batsman} that yielded no runs during {temporal_phrase}?",
        "What's the total count of dot balls faced by {batsman} from {bowler} in the {temporal_phrase}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 39,
    "question": "Find the batsman who scored the most runs against {bowler} in the entire match. How many runs did he score overall against the bowler and how many runs did he score {temporal_phrase} regardless of bowler?",
    "query": "SELECT              batsman,              SUM(CASE WHEN bowler = '{bowler}' THEN batsman_runs ELSE 0 END) AS total_runs_batsman,              SUM(CASE WHEN {temporal_predicate} THEN batsman_runs ELSE 0 END) AS runs_between_x1_x2_batsman            FROM {table_name}            GROUP BY batsman            HAVING              SUM(CASE WHEN bowler = '{bowler}' THEN batsman_runs ELSE 0 END) = (                SELECT MAX(runs_vs_bowler)                FROM (                  SELECT SUM(batsman_runs) AS runs_vs_bowler                  FROM {table_name}                  WHERE bowler = '{bowler}'                  GROUP BY batsman                ) t              );",
    "exp": "First, find the batsman who scored the most runs against the specified bowler in the entire match. Then calculate how many runs that batsman scored between overs x1 and x2 irrespective of which bowler bowled. Finally, return the batsman's name, total runs against the bowler, and runs scored in the specified over range.",
    "variables": ["table_name", "bowler", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "{temporal_phrase}, identify the batsman who not only scored the most runs but also hit the most sixes specifically against {bowler}.",
        "Which batsman dominated {bowler} by scoring the highest runs and hitting the most sixes during {temporal_phrase}?",
        "Who was the top scorer and top six-hitter against {bowler} in the {temporal_phrase} period?"
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 41,
    "question": "Calculate the total number of sixes hit by batsmen against {bowler} {temporal_phrase}",
    "query": "SELECT COALESCE(SUM(batsman_sixes), 0) AS total_sixes_batsman FROM {table_name} WHERE bowler = '{bowler}' AND {temporal_predicate};",
    "exp": "Sum the number of sixes hit by all batsmen against the specified bowler within the overs range from x1 to x2. If no sixes are found, return zero.",
    "variables": ["table_name", "bowler", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "What's the total number of sixes batsmen scored against {bowler} during {temporal_phrase}?",
        "How many maximums (sixes) were hit off {bowler}'s bowling in total {temporal_phrase}?",
        "Can you tell me the combined count of sixes hit by batsmen when facing {bowler} from {temporal_phrase}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 42,
    "question": "Calculate the total number of dots hit by {batsman} against {bowler} {temporal_phrase}",
    "query": "SELECT COUNT(*) AS total_dots FROM {table_name} WHERE batsman = '{batsman}' AND bowler = '{bowler}' AND team_runs = 0 AND {temporal_predicate};",
    "exp": "Count all deliveries between overs x1 and x2 where the specified batsman faced the specified bowler and no runs were scored on that ball (dot balls).",
    "variables": ["table_name", "batsman", "bowler", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many dot balls did {batsman} play when facing {bowler} {temporal_phrase}?",
        "Can you count the number of deliveries {bowler} bowled to {batsman} that yielded no runs during {temporal_phrase}?",
        "What's the total count of dot balls faced by {batsman} from {bowler} in the {temporal_phrase}?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 43,
    "question": "Find the batsman who scored the most runs against {bowler} and how many sixes did he hit in {temporal_phrase}?",
    "query": "WITH runs_vs AS (              SELECT                batsman,                SUM(batsman_runs) AS runs_vs_bowler              FROM {table_name}              WHERE bowler = '{bowler}'              GROUP BY batsman            ),            max_runs AS (              SELECT MAX(runs_vs_bowler) AS mx FROM runs_vs            )            SELECT              t.batsman,              rv.runs_vs_bowler AS total_runs_batsman,              SUM(CASE WHEN {temporal_predicate}                      THEN t.batsman_sixes ELSE 0 END) AS sixes_between_overs            FROM {table_name} t            JOIN runs_vs rv              ON rv.batsman = t.batsman            CROSS JOIN max_runs m            WHERE rv.runs_vs_bowler = m.mx            GROUP BY t.batsman, rv.runs_vs_bowler;",
    "exp": "First, identify the batsman who scored the most runs against the specified bowler throughout the match. Then, for that batsman, count how many sixes he hit in the overs between x1 and x2 (regardless of bowler). Finally, return the batsman’s name, total runs against the bowler, and sixes hit in the specified overs.",
    "variables": ["table_name", "bowler", "temporal_phrase", "temporal_predicate","t"],
    "paraphrases": [
        "{temporal_phrase}, identify the batsman who not only scored the most runs but also hit the most sixes specifically against {bowler}.",
        "Which batsman dominated {bowler} by scoring the highest runs and hitting the most sixes during {temporal_phrase}?",
        "Who was the top scorer and top six-hitter against {bowler} in the {temporal_phrase}?"
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 44,
    "question": "List all batsmen and the total number of runs they scored against {bowler}.",
    "query": "SELECT batsman, SUM(batsman_runs) AS total_runs FROM {table_name} WHERE bowler = '{bowler}' GROUP BY batsman ORDER BY total_runs DESC;",
    "exp": "This query filters the match data to include only the deliveries bowled by the specified bowler. It then groups the data by each batsman and calculates the total runs each batsman scored against that bowler. Finally, it orders the results in descending order of total runs to identify the top-scoring batsman against the given bowler.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "Show me a list of all batsmen and the runs they accumulated when facing {bowler}.",
        "For each batsman, how many runs did they score specifically off {bowler}'s bowling?",
        "Provide a breakdown of total runs scored by every batsman against {bowler}."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 45,
    "question": "Show each bowler and the total number of sixes hit against them by {batsman}.",
    "query": "SELECT bowler, SUM(CASE WHEN batsman_runs = 6 THEN 1 ELSE 0 END) AS sixes_hit FROM {table_name} WHERE batsman = '{batsman}' GROUP BY bowler ORDER BY sixes_hit DESC;",
    "exp": "Filters the data to include only the deliveries faced by the specified batsman. Then group the data by bowler and count how many sixes (where batsman_runs = 6) the batsman hit against each bowler. The results are ordered in descending order of sixes to identify the bowler against whom the batsman hit the most sixes.",
    "variables": ["table_name", "batsman"],
    "paraphrases": [
        "For {batsman}, show me how many sixes they hit against each individual bowler.",
        "List each bowler and the total count of sixes {batsman} scored off their bowling.",
        "How many maximums did {batsman} hit against each bowler they faced?"
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 46,
    "question": "List all batsmen and how many deliveries they faced from {bowler}.",
    "query": "SELECT batsman, COUNT(*) AS balls_faced FROM {table_name} WHERE bowler = '{bowler}' GROUP BY batsman ORDER BY balls_faced DESC;",
    "exp": "Filters the data to include only the deliveries bowled by the specified bowler. Then groups the records by batsman and counts the number of deliveries each batsman faced from the bowler. The results are ordered in descending order of balls faced to identify the batsman who faced the most deliveries from the bowler.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "Show me which batsmen faced {bowler}, and the number of balls each of them received.",
        "For every batsman, how many deliveries did {bowler} bowl to them?",
        "Provide a list of batsmen and the total balls they faced from {bowler}."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 47,
    "question": "List all overs where {batsman} faced {bowler}, and how many runs they scored in each over.",
    "query": "SELECT Ceil(overs) AS over_number, SUM(batsman_runs) AS runs_in_over FROM {table_name} WHERE batsman = '{batsman}' AND bowler = '{bowler}' GROUP BY Ceil(overs) ORDER BY over_number;",
    "exp": "Break down how many runs a specific batsman scored against a particular bowler in each over. It uses Ceil(overs) to convert the fractional over values into whole numbers (i.e., groups all deliveries from the same over together). Then, it sums up the batsman's runs for each over where the bowler was involved. Finally, it orders the results by the over number to show the progression of runs scored across overs.",
    "variables": ["table_name", "batsman", "bowler"],
    "paraphrases": [
        "For each over that {batsman} faced {bowler}, tell me how many runs {batsman} scored.",
        "Show me every over in which {batsman} was batting against {bowler}, and the runs {batsman} scored in those overs.",
        "Break down {batsman}'s runs per over when facing {bowler}."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 48,
    "question": "Show the total runs and number of dot balls faced by each batsman against {bowler}.",
    "query": "SELECT batsman, SUM(batsman_runs) AS total_runs, SUM(CASE WHEN team_runs = 0 THEN 1 ELSE 0 END) AS dot_balls FROM {table_name} WHERE bowler = '{bowler}' GROUP BY batsman ORDER BY total_runs DESC;",
    "exp": "This query retrieves each batsman's total runs scored against the specified bowler, as well as the number of dot balls they played (i.e., deliveries where team_runs = 0). It groups the records by batsman and sorts the output by total runs in descending order to identify the top scorer.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "For each batsman who faced {bowler}, provide their total runs and the count of dot balls.",
        "List all batsmen, their runs scored, and dot balls faced when up against {bowler}.",
        "What are the total runs and dot balls for each batsman against {bowler}?"
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 49,
    "question": "List batsman-bowler pairs and the total number of deliveries between them where at least one boundary (4 or 6) was hit.",
    "query": "SELECT batsman, bowler, COUNT(*) AS boundary_deliveries FROM {table_name} WHERE batsman_runs IN (4, 6) GROUP BY batsman, bowler ORDER BY boundary_deliveries DESC;",
    "exp": "This query counts the number of deliveries that resulted in a boundary (either a four or a six) for each unique batsman-bowler pair. It groups the data by both batsman and bowler, then orders the result by the count of boundary deliveries in descending order to highlight the most aggressive batsman-bowler combinations.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each batsman-bowler pairing, tell me how many deliveries resulted in a boundary (four or six).",
        "Show me pairs of batsmen and bowlers, and the total balls they bowled to each other where a 4 or 6 was scored.",
        "Which batsman-bowler matchups produced at least one boundary, and on how many balls did this occur?"
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 50,
    "question": "Show the count of boundaries (4s and 6s) hit by {batsman} against {bowler} in each over, including overs where zero boundaries were hit.",
    "query": "WITH relevant_overs AS (             SELECT DISTINCT Ceil(overs) AS over_number             FROM {table_name}             WHERE batsman = '{batsman}' AND bowler = '{bowler}'             ),             boundary_counts AS (             SELECT Ceil(overs) AS over_number,                     COUNT(*) AS boundaries             FROM {table_name}             WHERE batsman = '{batsman}' AND bowler = '{bowler}'             AND batsman_runs IN (4,6)             GROUP BY Ceil(overs)             )             SELECT relevant_overs.over_number AS overs,                 COALESCE(boundary_counts.boundaries, 0) AS boundaries             FROM relevant_overs             LEFT JOIN boundary_counts             ON relevant_overs.over_number = boundary_counts.over_number             ORDER BY relevant_overs.over_number;",
    "exp": "This query lists all overs bowled in the match and counts the number of boundaries (4s and 6s) the specified batsman hit against the specified bowler in each over. If no boundaries were hit in an over, it shows 0 for that over.",
    "variables": ["table_name", "batsman", "bowler"],
    "paraphrases": [
        "For every over {batsman} batted against {bowler}, indicate how many fours or sixes were hit.",
        "Show me the overs where {batsman} faced {bowler}, and the boundary count (4s and 6s) in each of those overs.",
        "Break down the boundaries (fours/sixes) hit by {batsman} against {bowler} for each over they faced off."
    ],
    "primary_key": ["overs"]
    },
    {
    "id": 51,
    "question": "List all batsmen who hit at least one six against {bowler}, with total runs against the bowler and number of sixes.",
    "query": "SELECT batsman, SUM(batsman_runs) AS total_runs, SUM(CASE WHEN batsman_runs = 6 THEN 1 ELSE 0 END) AS total_sixes FROM {table_name} WHERE bowler = '{bowler}' GROUP BY batsman HAVING total_sixes > 0 ORDER BY total_sixes DESC;",
    "exp": "This query finds all batsmen who hit at least one six off the given bowler, calculates their total runs and total sixes against that bowler, and orders the results with the batsmen who hit the most sixes at the top.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "Which batsmen hit at least one six off {bowler}, and what were their total runs and sixes count?",
        "Show me the batsmen who hit one or more sixes against {bowler}, along with their total runs and the number of sixes they scored.",
        "For {bowler}, list the batsmen who hit at least one maximum, displaying their total runs and the count of sixes."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 52,
    "question": "Show all batsmen and their dot ball percentages against {bowler} (if faced at least 6 balls). Consider all interactions between batsman and bowler as bowls faced.",
    "query": "SELECT batsman, ROUND(100.0 * SUM(CASE WHEN team_runs = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS dot_ball_percentage, COUNT(*) AS balls_faced FROM {table_name} WHERE bowler = '{bowler}' GROUP BY batsman HAVING balls_faced >= 6 ORDER BY dot_ball_percentage DESC;",
    "exp": "This query calculates for each batsman the percentage of deliveries bowled by bowler that resulted in zero runs (dot balls). It only includes batsmen who faced 6 or more balls, and sorts the results so that batsmen with the highest dot ball percentages appear first.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "For batsmen who faced at least 6 balls from {bowler}, what's their dot ball percentage?",
        "Show the percentage of dot balls for each batsman against {bowler}, but only for those who faced 6 or more deliveries.",
        "Calculate and display the dot ball percentage for all batsmen facing {bowler}, provided they faced a minimum of 6 balls."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 53,
    "question": "List every batsman-bowler pair with total runs, balls faced, and boundaries (4 or 6) between them.",
    "query": "SELECT batsman, bowler, SUM(batsman_runs) AS total_runs, COUNT(*) AS balls_faced, SUM(CASE WHEN batsman_runs IN (4,6) THEN 1 ELSE 0 END) AS boundaries FROM {table_name} GROUP BY batsman, bowler ORDER BY total_runs DESC;",
    "exp": "This query groups data by each batsman and bowler pair, calculates the total runs scored by the batsman against that bowler, counts how many balls the batsman faced from that bowler, and counts how many of those deliveries were boundaries (fours or sixes). The results are sorted with the highest total runs first.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each unique batsman-bowler combination, provide the total runs scored, balls faced, and the number of boundaries (fours or sixes).",
        "Show me a comprehensive list of every batsman and bowler pair, detailing their total runs scored against each other, the balls exchanged, and the boundaries hit.",
        "Summarize the performance of each batsman against every bowler, including total runs, deliveries faced, and boundaries hit."
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 54,
    "question": "List all sequences of 3 consecutive sixes hit by batsmen and on which balls.",
    "query": "SELECT t1.batsman, t1.overs AS ball_1, t2.overs AS ball_2, t3.overs AS ball_3 FROM {table_name} t1 JOIN {table_name} t2 ON t2.overs = t1.overs + 0.1 AND t2.batsman = t1.batsman JOIN {table_name} t3 ON t3.overs = t2.overs + 0.1 AND t3.batsman = t1.batsman WHERE t1.batsman_runs = 6 AND t2.batsman_runs = 6 AND t3.batsman_runs = 6 ORDER BY t1.batsman, t1.overs;",
    "exp": "Self-joins the table three times to find sequences of three consecutive deliveries (by overs incremented by 0.1) where the same batsman scored six runs on each ball. It returns the batsman and the overs of these three sixes, ordered by batsman and over.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify all instances where a batsman hit three consecutive sixes, and specify the ball numbers for each six.",
        "Show me every occurrence of a batsman hitting a hat-trick of sixes, indicating the exact deliveries on which they occurred.",
        "Find all sequences of three back-to-back sixes by batsmen, along with the specific ball progression for each sequence."
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 55,
    "question": "Show wides bowled by each bowler per over.",
    "query": "SELECT Ceil(overs) AS over_number, bowler, COUNT(*) AS wides FROM {table_name} WHERE runs like '%w%' GROUP BY Ceil(overs), bowler ORDER BY over_number, bowler;",
    "exp": "This query groups deliveries by over (using the floor of the overs) and bowler, counting how many wides (indicated by 'w' in the runs column) were bowled in each over by each bowler, ordered by over and bowler.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, how many wides did each bowler deliver?",
        "Show me a breakdown of wides bowled by every bowler, organized by over.",
        "List the number of wide deliveries per over for each bowler."
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 56,
    "question": "Show no balls bowled by each bowler per over.",
    "query": "SELECT Ceil(overs) AS over_number, bowler, COUNT(*) AS no_balls FROM {table_name} WHERE runs LIKE '%nb%' GROUP BY Ceil(overs), bowler ORDER BY over_number, bowler;",
    "exp": "This query groups deliveries by over (using the floor of the overs) and bowler, counting how many no balls (indicated by 'nb' in the runs column) were bowled in each over by each bowler, ordered by over and bowler.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, how many no-balls did each bowler deliver?",
        "Show me a breakdown of no-balls bowled by every bowler, organized by over.",
        "List the number of illegal deliveries (no-balls) per over for each bowler."
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 57,
    "question": "List batsmen and total runs they scored on no balls per bowler.",
    "query": "SELECT bowler, batsman, SUM(batsman_runs) AS runs_on_no_balls FROM {table_name} WHERE runs LIKE '%nb%' GROUP BY bowler, batsman ORDER BY bowler, runs_on_no_balls DESC;",
    "exp": "This query calculates the total runs scored by each batsman off no balls bowled by each bowler. It filters deliveries with 'nb' in the runs column, groups by bowler and batsman, sums the batsman runs for these deliveries, and orders the results by bowler and descending runs scored on no balls.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each bowler, show me the batsmen who scored runs off their no-balls, and the total runs each batsman accumulated.",
        "List batsmen and the runs they scored from no-balls, categorized by the bowler who bowled them.",
        "How many runs did each batsman score off no-balls bowled by specific bowlers?"
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 58,
    "question": "Show extra runs conceded through wides and no balls by each bowler, per over.",
    "query": "SELECT Ceil(overs) AS over_number, bowler, SUM(team_runs-batsman_runs) AS extras_in_over FROM {table_name} WHERE runs LIKE '%w%' OR runs LIKE '%nb%' GROUP BY Ceil(overs), bowler ORDER BY over_number, bowler;",
    "exp": "This query calculates the extras conceded by each bowler in each over by summing the difference between team runs and batsman runs for deliveries marked as wides or no balls. It groups the results by over number and bowler, ordering them by over and bowler.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, show the extra runs (wides and no-balls) conceded by each bowler.",
        "Break down the additional runs given away by each bowler (due to wides and no-balls) on an over-by-over basis.",
        "List the over-by-over extra runs conceded by each bowler specifically from wides and no-balls."
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 59,
    "question": "Show batsmen and how many runs they scored on no ball deliveries from each bowler.",
    "query": "SELECT batsman, bowler, SUM(batsman_runs) AS runs_on_no_balls FROM {table_name} WHERE runs LIKE '%nb%' GROUP BY batsman, bowler ORDER BY runs_on_no_balls DESC;",
    "exp": "This query finds the total runs scored by each batsman off no-ball deliveries, grouped by both batsman and bowler. It helps identify which batsman took the most advantage of no balls and against which bowler.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each batsman, how many runs did they score from no-ball deliveries against specific bowlers?",
        "List batsmen and the runs they made off no-balls, showing which bowler delivered them.",
        "Provide a summary of runs scored by each batsman on no-balls, broken down by the bowler."
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 60,
    "question": "List total extras conceded by each bowling team in each over.",
    "query": "SELECT Ceil(overs) AS over_number, SUM(CASE WHEN runs LIKE '%w%' THEN 1 ELSE 0 END) AS wides, SUM(CASE WHEN runs LIKE '%nb%' THEN 1 ELSE 0 END) AS no_balls, SUM(CASE WHEN runs LIKE '%b%' AND runs NOT LIKE '%nb%' AND runs NOT LIKE '%w%' THEN 1 ELSE 0 END) AS byes, SUM(CASE WHEN runs LIKE '%lb%' THEN 1 ELSE 0 END) AS leg_byes, COUNT(*) AS total_extras_in_over FROM {table_name} WHERE runs LIKE '%w%' OR runs LIKE '%nb%' OR runs LIKE '%b%' OR runs LIKE '%lb%' GROUP BY Ceil(overs) ORDER BY over_number; ",
    "exp": "This query breaks down the number of different types of extras—wides, no balls, byes, and leg byes—recorded in each over. It groups deliveries by over number and counts each type of extra delivery, helping assess bowling discipline across the innings.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, show the total extra runs given up by the fielding team, including wides, no-balls, byes, and leg-byes.",
        "Provide an over-by-over breakdown of all extras conceded by the batting team.",
        "List the total number of wides, no-balls, byes, and leg-byes conceded by the batting team in each over."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 61,
    "question": "Show runs scored after no ball deliveries, by batsman and bowler pair.",
    "query": "WITH numbered_balls AS ( \
        SELECT *, \
            ROW_NUMBER() OVER (PARTITION BY bowler ORDER BY overs) AS rn \
        FROM {table_name} \
        ), \
        no_ball_deliveries AS ( \
            SELECT bowler, overs, rn \
            FROM numbered_balls \
            WHERE runs LIKE '%nb%' \
        ), \
        next_balls AS ( \
            SELECT nb.bowler, b.batsman, b.team_runs \
            FROM no_ball_deliveries nb \
            JOIN numbered_balls b \
            ON nb.bowler = b.bowler AND b.rn = nb.rn + 1 \
        ) \
        SELECT bowler, batsman, SUM(team_runs) AS runs_after_no_ball \
        FROM next_balls \
        GROUP BY bowler, batsman \
        ORDER BY runs_after_no_ball DESC;",
    "exp": "This query finds how many runs were scored on the delivery immediately following a no-ball for each bowler and batsman. First, it assigns a row number to each delivery by a bowler using the ROW_NUMBER() function (numbered_balls CTE). Then it filters the rows with no-balls (no_ball_deliveries CTE). After that, it joins each no-ball delivery with the very next delivery (next_balls CTE) based on the row number. Finally, it sums up the team runs scored on those next balls, grouping the result by bowler and batsman.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each bowler-batsman pair, show the total runs scored on the delivery immediately following a no-ball.",
        "When a no-ball is bowled, how many runs are scored on the next legal delivery, broken down by bowler and the batsman who faced it?",
        "List the runs accumulated after no-ball deliveries, categorized by the bowler who bowled the no-ball and the batsman who faced the subsequent delivery."
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 62,
    "question": "Show each bowler's number of hat-tricks of wides (3 consecutive balls) with start ball.",
    "query": "WITH numbered_balls AS ( \
                SELECT *, \
                    ROW_NUMBER() OVER (PARTITION BY bowler ORDER BY overs) AS rn \
                FROM {table_name} \
            ), \
            wide_balls AS ( \
                SELECT bowler, overs, rn \
                FROM numbered_balls \
                WHERE runs LIKE '%w%' \
            ), \
            consecutive_wides AS ( \
                SELECT w1.bowler, w1.overs AS wide_1, w2.overs AS wide_2, w3.overs AS wide_3 \
                FROM wide_balls w1 \
                JOIN wide_balls w2 ON w1.bowler = w2.bowler AND w2.rn = w1.rn + 1 \
                JOIN wide_balls w3 ON w1.bowler = w3.bowler AND w3.rn = w2.rn + 1 \
            ) \
            SELECT * FROM consecutive_wides \
            ORDER BY bowler, wide_1;",
    "exp": "Use ROW_NUMBER to assign a sequential index to each delivery bowled by each bowler. Then filter the wide deliveries and look for sequences where three consecutive rows (based on row number) are all wides by the same bowler",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify instances where a bowler delivered three consecutive wides, showing the bowler and the ball numbers for each wide.",
        "List all hat-tricks of wides bowled by each bowler, indicating the starting ball of each sequence.",
        "Find every time a bowler bowled three consecutive wide deliveries, specifying the bowler and the sequence of balls."
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 63,
    "question": "Show total runs scored in each over with number of wickets fallen.",
    "query": "SELECT Ceil(overs) AS over_number, SUM(team_runs) AS total_runs, SUM(CASE WHEN runs like '%W%' THEN 1 ELSE 0 END) AS wickets_in_over FROM {table_name} GROUP BY Ceil(overs) ORDER BY over_number;",
    "exp": "This query calculates per-over totals by rounding down the 'overs' field to group all deliveries in the same over. It sums up the team_runs for total runs and uses a conditional count to tally how many wickets ('W') were recorded in the 'runs' column within each over. The results are ordered by over number.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, what were the total runs scored and the number of wickets that fell?",
        "Provide an over-by-over summary of runs scored and wickets lost.",
        "List the total runs and wickets for every over of the match."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 64,
    "question": "Show runs conceded and extras per over by each bowler.",
    "query": "SELECT Ceil(overs) AS over_number, bowler, SUM(team_runs) AS runs_in_over, SUM(team_runs-batsman_runs) AS extras_in_over FROM {table_name} GROUP BY Ceil(overs), bowler ORDER BY over_number, bowler;",
    "exp": "This query groups the data by over number (using FLOOR on the overs field) and by bowler. It calculates the total runs conceded in the over (`SUM(team_runs)`) and the number of extras (`SUM(team_runs - batsman_runs)`) assuming extras are the difference between team and batsman runs. The results are ordered by over number and bowler.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, how many runs (including extras) did each bowler concede?",
        "Break down the runs given away and the extras bowled by each bowler on an over-by-over basis.",
        "List runs conceded and extras per over for every bowler in the match."
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 65,
    "question": "Show total runs, wickets, wides, and no balls in each over.",
    "query": "SELECT Ceil(overs) AS over_number, SUM(team_runs) AS total_runs, SUM(bowler_wickets) AS wickets, SUM(CASE WHEN runs LIKE '%w%' THEN 1 ELSE 0 END) AS wides, SUM(CASE WHEN runs LIKE '%nb%' THEN 1 ELSE 0 END) AS no_balls FROM {table_name} GROUP BY Ceil(overs) ORDER BY over_number;",
    "exp": "FLOOR on the 'overs' column. For each over, it calculate the total runs scored, total wickets taken, and count the number of wides and no balls by checking if the 'runs' column contains 'w' or 'nb' respectively. The results are ordered chronologically by over number.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, provide a summary of total runs, wickets, wides, and no-balls.",
        "Show me the runs, wickets, wides, and no-balls for every over in the game.",
        "List the over number, total runs, wickets taken, wides bowled, and no-balls bowled for each over."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 66,
    "question": "Show runs scored by each batsman in each over.",
    "query": "SELECT Ceil(overs) AS over_number, batsman, SUM(batsman_runs) AS runs_in_over FROM {table_name} GROUP BY Ceil(overs), batsman ORDER BY over_number, batsman;",
    "exp": "This query calculates how many runs each batsman scored in each over by grouping the data using the floored over number and batsman name. It then sums up the batsman_runs for each batsman-over pair and orders the result by over number and batsman alphabetically.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, how many runs did each batsman score?",
        "Break down the runs scored by every batsman on an over-by-over basis.",
        "List the over number, batsman, and runs scored by that batsman in each over."
    ],
    "primary_key": ["over_number", "batsman"]
    },
    {
    "id": 67,
    "question": "Show number of balls faced by each batsman in each over.",
    "query": "SELECT Ceil(overs) AS over_number, batsman, SUM(batsman_bowls_faced) AS balls_faced FROM {table_name} GROUP BY Ceil(overs), batsman ORDER BY over_number, batsman;",
    "exp": "This query calculates the total number of balls faced by each batsman in each over. It does this by grouping the records by the floored over number and batsman name, summing the 'batsman_bowls_faced' field for each group, and sorting the results by over number and batsman.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, how many balls did each batsman face?",
        "Provide an over-by-over account of balls faced by every batsman.",
        "List the over number, batsman, and the count of balls faced by that batsman in each over."
    ],
    "primary_key": ["over_number", "batsman"]
    },
    {
    "id": 68,
    "question": "Show number of dot balls bowled in each over.",
    "query": "SELECT Ceil(overs) AS over_number, COUNT(*) AS dot_balls FROM {table_name} WHERE team_runs = 0 GROUP BY Ceil(overs) ORDER BY over_number;",
    "exp": "Dot balls (deliveries where no runs were scored) bowled in each over. It filters rows where team_runs equals 0, groups them by the over number (using FLOOR to group fractional ball values into whole overs), counts the entries for each group, and orders the output by over number.",
    "variables": ["table_name"],
    "paraphrases": [
        "How many dot balls were bowled in each over?",
        "Provide a count of dot balls for every over of the match.",
        "List the number of deliveries in each over where no runs were scored."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 69,
    "question": "Show progression of cumulative score after each over.",
    "query": "SELECT Ceil(overs) AS over_number, SUM(team_runs) AS runs_in_over, SUM(SUM(team_runs)) OVER (ORDER BY Ceil(overs)) AS cumulative_runs FROM {table_name} GROUP BY Ceil(overs) ORDER BY over_number;",
    "exp": "Group the deliveries by the integer part of the over number, sum the team_runs per group, and then uses a window function to calculate a running total (cumulative sum) of these over-wise sums, ordered by over number.",
    "variables": ["table_name"],
    "paraphrases": [
        "What was the total score after each over, showing the cumulative progression?",
        "Display the runs scored in each over and the running total of runs after every over.",
        "Track the cumulative score over the course of the match, showing the total after each over."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 70,
    "question": "Show cumulative wickets(bolwer credited) after each over.",
    "query": "SELECT Ceil(overs) AS over_number, SUM(bowler_wickets) AS wickets_in_over, SUM(SUM(bowler_wickets)) OVER (ORDER BY Ceil(overs)) AS cumulative_wickets FROM {table_name} GROUP BY Ceil(overs) ORDER BY over_number;",
    "exp": "It groups data by over number, counts the number of entries where a wicket was taken (assuming 'bowler_wickets' indicates that), and then uses a window function to compute the running total of wickets in over-wise order.",
    "variables": ["table_name"],
    "paraphrases": [
        "What was the total number of wickets fallen after each over (bolwer credited), showing the cumulative progression?",
        "Display the wickets taken in each over (bolwer credited) and the running total of wickets after every over.",
        "Track the cumulative wickets over the course of the match (bolwer credited), showing the total after each over."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 71,
    "question": "Show total runs scored in each over where the batting team has hit atleast 1 six.",
    "query": "SELECT               CEIL(overs) AS over_number,               SUM(team_runs) AS runs_in_over             FROM {table_name}             GROUP BY CEIL(overs)             HAVING SUM(CASE WHEN batsman_runs = 6 THEN 1 ELSE 0 END) > 0             ORDER BY over_number ASC;",
    "exp": "It groups all deliveries by their over number using Ceil(overs) to remove the decimal part and sums up the team_runs for each over. The results are ordered in increasing over number.",
    "variables": ["table_name"],
    "paraphrases": [
        "How many runs were scored in each over where atleast a 6 was hit?",
        "Provide a breakdown of total runs per over where atleast one six was hit.",
        "List the runs scored in every over of the match where atleast one six was hit."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 72,
    "question": "Show total runs per over by batting team.",
    "query": "SELECT Ceil(overs) AS over_number, SUM(team_runs) AS runs_in_over FROM {table_name} GROUP BY Ceil(overs) ORDER BY over_number;",
    "exp": "This query calculates the total number of runs scored in each over. It first groups all deliveries by their over number using Ceil(overs), which converts values like 4.2 or 4.6 to just 4. Then, for each over, it sums the team_runs to compute the total runs scored during that over. Finally, the results are ordered by the over number to show the progression of scoring throughout the innings.",
    "variables": ["table_name"],
    "paraphrases": [
        "What was the batting team's total run count for each over?",
        "Display the runs scored by the batting team in every over.",
        "List the runs accumulated by the batting side per over."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 74,
    "question": "Show cumulative total runs after each over by batting team.",
    "query": "SELECT Ceil(overs) AS over_number, SUM(team_runs) AS runs_in_over, SUM(SUM(team_runs)) OVER (ORDER BY Ceil(overs)) AS cumulative_runs FROM {table_name} GROUP BY Ceil(overs) ORDER BY over_number;",
    "variables": ["table_name"],
    "paraphrases": [
        "What was the batting team's cumulative score after each over?",
        "Display the runs scored by the batting team in each over, and their running total after every over.",
        "Track the batting team's cumulative runs, showing the total after each completed over."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 75,
    "question": "Show 3-over moving average of runs to detect momentum shifts.",
    "query": "SELECT over_number, AVG(runs_in_over) OVER (ORDER BY over_number ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS moving_avg_runs FROM (  SELECT Ceil(overs) AS over_number,   SUM(team_runs) AS runs_in_over   FROM {table_name}   GROUP BY Ceil(overs) ) AS overwise_runs ORDER BY over_number;",
    "exp": "This query calculates a 3-over moving average of runs scored. First, it aggregates total team runs for each over using Ceil(overs) and stores it as 'runs_in_over'. Then, using a window function, it computes the average of the current over and the two preceding overs. This helps to smooth out fluctuations and analyze short-term scoring trends across overs.",
    "variables": ["table_name"],
    "paraphrases": [
        "Calculate and display the 3-over rolling average of runs to identify changes in momentum.",
        "Show the average runs scored over every three consecutive overs, indicating momentum shifts.",
        "What's the 3-over moving average of runs, useful for analyzing game momentum?"
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 76,
    "question": "Show 5-over moving average of runs by batting team.",
    "query": "SELECT over_number, AVG(runs_in_over) OVER (ORDER BY over_number ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS moving_avg_runs FROM (  SELECT Ceil(overs) AS over_number,   SUM(team_runs) AS runs_in_over   FROM {table_name}   GROUP BY Ceil(overs) ) AS overwise_runs ORDER BY over_number;",
    "exp": "This query calculates a 5-over moving average of runs scored. First, it aggregates total team runs for each over using Ceil(overs) and stores it as 'runs_in_over'. Then, using a window function, it computes the average of the current over and the two preceding overs. This helps to smooth out fluctuations and analyze short-term scoring trends across overs.",
    "variables": ["table_name"],
    "paraphrases": [
        "Calculate and display the 5-over rolling average of runs for the batting team.",
        "Show the average runs scored by the batting team over every five consecutive overs.",
        "What's the 5-over moving average of runs for the team currently batting?"
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 77,
    "question": "Show total runs scored by each batsman {temporal_phrase}.",
    "query": "SELECT batsman, SUM(batsman_runs) AS runs_scored FROM {table_name} WHERE {temporal_predicate} GROUP BY batsman ORDER BY runs_scored DESC;",
    "exp": "It groups the data by batsman and sums their runs in that over range, then orders the results to show the highest scorers first.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many runs did each batsman score during {temporal_phrase}?",
        "List the total runs accumulated by every batsman within the specified ({temporal_phrase}).",
        "Provide a breakdown of runs scored by each batsman {temporal_phrase}."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 78,
    "question": "Show number of balls faced including extras by each batsman {temporal_phrase}.",
    "query": "SELECT               batsman,               COUNT(*) AS balls_faced             FROM {table_name}             WHERE {temporal_predicate}             GROUP BY batsman             ORDER BY balls_faced DESC, batsman ASC;",
    "exp": "This query counts the number of balls faced by each batsman between overs {x1} and {x2}. It groups the data by batsman, counts their deliveries in the specified over range, and orders the results to show the batsmen who faced the most balls first.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many balls did each batsman face {temporal_phrase}?",
        "List the total deliveries faced by every batsman within the specified {temporal_phrase}.",
        "Provide a breakdown of balls faced by each batsman {temporal_phrase}."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 79,
    "question": "Show runs conceded by each bowler {temporal_phrase}.",
    "query": "SELECT               bowler,               SUM(bowler_runs_given) AS runs_conceded             FROM {table_name}             WHERE {temporal_predicate}             GROUP BY bowler             ORDER BY runs_conceded DESC, bowler ASC;",
    "exp": "It groups the data by bowler, sums the team runs conceded in that over range, and orders the results in descending order to identify the bowlers who gave away the most runs.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many runs did each bowler concede {temporal_phrase}?",
        "List the total runs given away by every bowler within the specified {temporal_phrase}.",
        "Provide a breakdown of runs conceded by each bowler {temporal_phrase}."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 80,
    "question": "Show total wickets taken by each bowler {temporal_phrase}.",
    "query": "SELECT               bowler,               SUM(bowler_wickets) AS wickets_taken             FROM {table_name}             WHERE {temporal_predicate}             GROUP BY bowler             HAVING SUM(bowler_wickets) > 0             ORDER BY wickets_taken DESC, bowler ASC;",
    "exp": "This query calculates the total number of wickets taken by each bowler between overs {x1} and {x2}. It groups the data by bowler, sums the wickets taken within the specified over range, and orders the results in descending order to show the bowlers with the most wickets in that period.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many wickets did each bowler take {temporal_phrase}?",
        "List the total wickets claimed by every bowler within the specified {temporal_phrase}.",
        "Provide a breakdown of wickets taken by each bowler {temporal_phrase}."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 81,
    "question": "Show number of dot balls bowled by each bowler {temporal_phrase}.",
    "query": "SELECT               bowler,               COUNT(*) AS dot_balls             FROM {table_name}             WHERE {temporal_predicate}               AND team_runs = 0             GROUP BY bowler             ORDER BY dot_balls DESC, bowler ASC;",
    "exp": "It groups the data by bowler, filters for deliveries with zero team runs in the specified overs range, and orders the result in descending order to show the bowlers with the most dot balls.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many dot balls did each bowler deliver {temporal_phrase}?",
        "List the total number of dot balls bowled by every bowler within the specified {temporal_phrase}.",
        "Provide a breakdown of dot balls bowled by each bowler {temporal_phrase}."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 82,
    "question": "Show number of sixes hit by each batsman {temporal_phrase}.",
    "query": "SELECT               batsman,               SUM(CASE WHEN batsman_runs = 6 THEN 1 ELSE 0 END) AS sixes_hit             FROM {table_name}             WHERE {temporal_predicate}             GROUP BY batsman             ORDER BY sixes_hit DESC, batsman ASC;",
    "exp": "It filters deliveries in that overs range, counts each six (where batsman_runs equals 6) for each batsman, groups the results by batsman, and orders them by the highest number of sixes.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many sixes did each batsman hit {temporal_phrase}?",
        "List the total number of maximums (6s) scored by every batsman within the specified {temporal_phrase}.",
        "Provide a breakdown of sixes hit by each batsman {temporal_phrase}."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 83,
    "question": "Show total extras conceded by each bowler {temporal_phrase}.",
    "query": "SELECT               bowler,               SUM(team_runs - batsman_runs) AS extras_conceded             FROM {table_name}             WHERE {temporal_predicate}             GROUP BY bowler             ORDER BY extras_conceded DESC, bowler ASC;",
    "exp": "This query calculates the total extras conceded by each bowler between overs {x1} and {x2}. It sums the difference between team_runs and batsman_runs for each delivery (which represents extras), groups the results by bowler, and orders the bowlers from the highest to lowest extras conceded.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many extra runs did each bowler concede {temporal_phrase}?",
        "List the total number of extras given away by every bowler within the specified {temporal_phrase}.",
        "Provide a breakdown of extras conceded by each bowler {temporal_phrase}."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 84,
    "question": "Show total runs and wickets per over {temporal_phrase}.",
    "query": "SELECT               CEIL(overs) AS over_number,               SUM(team_runs) AS runs_in_over,               SUM(bowler_wickets) AS wickets_in_over             FROM {table_name}             WHERE {temporal_predicate}             GROUP BY CEIL(overs)             ORDER BY over_number ASC;",
    "exp": "This query calculates the total runs scored and total wickets taken in each over between overs {x1} and {x2}. It groups deliveries by the integer part of the overs (i.e., over number), sums the runs and wickets in each over, and orders the results by the over number in ascending order.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "For each over {temporal_phrase}, what were the total runs scored and the number of wickets that fell?",
        "Provide an over-by-over summary of runs scored and wickets lost within the {temporal_phrase}.",
        "List the total runs and wickets for every over of the match from {temporal_phrase}."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 85,
    "question": "Show number of wides bowled by each bowler {temporal_phrase}.",
    "query": "SELECT bowler, SUM(CASE WHEN runs LIKE '%w%' THEN 1 ELSE 0 END) AS wides FROM {table_name} WHERE {temporal_predicate} GROUP BY bowler ORDER BY wides DESC;",
    "exp": "This query calculates the total number of wides conceded by each bowler {temporal_phrase}. It filters deliveries within the specified overs range, counts occurrences where the runs column indicates wides using a pattern match, groups results by bowler, and orders them in descending order of wides conceded.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many wides did each bowler deliver {temporal_phrase}?",
        "List the total number of wide deliveries bowled by every bowler within the specified {temporal_phrase}.",
        "Provide a breakdown of wides bowled by each bowler {temporal_phrase}."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 86,
    "question": "Show total runs scored by each batsman against each bowler.",
    "query": "SELECT               batsman,               bowler,               SUM(batsman_runs) AS total_runs             FROM {table_name}             GROUP BY batsman, bowler             ORDER BY total_runs DESC, batsman ASC, bowler ASC;",
    "exp": "This query calculates the total runs scored by each batsman against each bowler throughout the match. It groups the data by both batsman and bowler, sums the batsman runs for each pair, and orders the results by the highest total runs in descending order.",
    "variables": ["table_name"],
    "paraphrases": [
        "For every batsman-bowler matchup, how many runs did the batsman score?",
        "List the total runs scored by each batsman against every bowler they faced.",
        "Provide a breakdown of runs scored by each batsman when facing specific bowlers."
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 87,
    "question": "Show total balls faced by each batsman against each bowler.",
    "query": "SELECT               batsman,               bowler,               SUM(batsman_bowls_faced) AS balls_faced             FROM {table_name}             GROUP BY batsman, bowler             HAVING SUM(batsman_bowls_faced) > 0             ORDER BY balls_faced DESC, batsman ASC, bowler ASC;",
    "exp": "This query counts the number of deliveries each batsman faced from each bowler. It groups the data by batsman and bowler pairs, counts the total balls faced for each pair, and sorts the results in descending order of balls faced.",
    "variables": ["table_name"],
    "paraphrases": [
        "For every batsman-bowler matchup, how many balls did the batsman face?",
        "List the total deliveries faced by each batsman against every bowler they encountered.",
        "Provide a breakdown of balls faced by each batsman when up against specific bowlers."
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 88,
    "question": "Show total wickets taken by each bowler against each batsman.",
    "query": "SELECT               bowler,               batsman,               SUM(bowler_wickets) AS wickets_taken             FROM {table_name}             GROUP BY bowler, batsman             HAVING SUM(bowler_wickets) > 0             ORDER BY wickets_taken DESC, bowler ASC, batsman ASC;",
    "exp": "This query calculates the total number of wickets each bowler has taken against each batsman by summing the wickets for each bowler-batsman pair. It groups the data by bowler and batsman and orders the results to show the pairs with the highest wickets taken first.",
    "variables": ["table_name"],
    "paraphrases": [
        "For every bowler-batsman matchup, how many wickets did the bowler take?",
        "List the total wickets claimed by each bowler against every batsman they dismissed.",
        "Provide a breakdown of wickets taken by each bowler when bowling to specific batsmen."
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 89,
    "question": "Show number of dot balls bowled by each bowler to each batsman.",
    "query": "SELECT               bowler,               batsman,               COUNT(*) AS dot_balls             FROM {table_name}             WHERE team_runs = 0             AND bowler_bowls_done = 1             GROUP BY bowler, batsman             ORDER BY dot_balls DESC, bowler ASC, batsman ASC;",
    "exp": "This query counts the number of dot balls (deliveries where no runs were scored) bowled by each bowler to each batsman. It groups the data by bowler and batsman and orders the results to show the pairs with the highest number of dot balls first.",
    "variables": ["table_name"],
    "paraphrases": [
        "For every bowler-batsman matchup, how many dot balls did the bowler deliver?",
        "List the total number of dot balls bowled by each bowler to every batsman they faced.",
        "Provide a breakdown of dot balls bowled by each bowler when bowling to specific batsmen."
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 90,
    "question": "Show number of sixes hit by each batsman against each bowler.",
    "query": "SELECT               batsman,               bowler,               SUM(CASE WHEN batsman_runs = 6 THEN 1 ELSE 0 END) AS sixes_hit             FROM {table_name}             GROUP BY batsman, bowler             ORDER BY sixes_hit DESC, batsman ASC, bowler ASC;",
    "exp": "This query calculates the total number of sixes hit by each batsman against each bowler. It groups the records by batsman and bowler, counts the deliveries where six runs were scored, and orders the results from the highest to the lowest number of sixes.",
    "variables": ["table_name"],
    "paraphrases": [
        "For every batsman-bowler matchup, how many sixes did the batsman hit?",
        "List the total number of sixes scored by each batsman against every bowler they faced.",
        "Provide a breakdown of sixes hit by each batsman when facing specific bowlers."
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 91,
    "question": "Show total runs conceded by each bowler to each batsman in each over.",
    "query": "SELECT               CEIL(overs) AS over_number,               bowler,               batsman,               SUM(bowler_runs_given) AS runs_conceded             FROM {table_name}             GROUP BY CEIL(overs), bowler, batsman             ORDER BY over_number ASC, runs_conceded DESC, bowler ASC, batsman ASC;",
    "exp": "This query groups the match data by over (rounded down to the nearest integer), bowler, and batsman to calculate the total runs conceded by each bowler to each batsman in every over. It then orders the results by over number ascending and runs conceded descending, showing which batsmen scored the most runs off which bowlers in each over.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, how many runs did each bowler concede to each specific batsman?",
        "List the runs given away by every bowler to individual batsmen, broken down by over.",
        "Provide an over-by-over summary of runs conceded by each bowler to each batsman."
    ],
    "primary_key": ["over_number", "bowler", "batsman"]
    },
    {
    "id": 92,
    "question": "Show batting strike rate of each batsman against each bowler.",
    "query": "SELECT               batsman,               bowler,               SUM(batsman_runs) AS total_runs,               SUM(batsman_bowls_faced) AS balls_faced,               ROUND((SUM(batsman_runs) * 100.0) / NULLIF(SUM(batsman_bowls_faced), 0), 2) AS strike_rate             FROM {table_name}             GROUP BY batsman, bowler             HAVING SUM(batsman_bowls_faced) > 0             ORDER BY strike_rate DESC, total_runs DESC, batsman ASC, bowler ASC;",
    "exp": "This query calculates the total runs scored by each batsman against each bowler, counts the total balls faced by the batsman from that bowler, and computes the strike rate (runs per 100 balls) for each batsman-bowler pair. The results are grouped by batsman and bowler, and then ordered by strike rate in descending order to show the most efficient batting performances against each bowler.",
    "variables": ["table_name"],
    "paraphrases": [
        "Calculate the strike rate for each batsman when facing every individual bowler.",
        "For every batsman-bowler encounter, what was the batsman's strike rate?",
        "List the batting strike rate of each batsman against specific bowlers they faced."
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 93,
    "question": "Show economy rate of each bowler against each batsman. Do not include byes or extras to calculate runs conceeded",
    "query": "SELECT               bowler,               batsman,               SUM(batsman_runs) AS total_runs_conceded,               SUM(bowler_bowls_done)   AS balls_bowled,               ROUND((SUM(batsman_runs) * 6.0) / NULLIF(SUM(bowler_bowls_done), 0), 2) AS economy_rate             FROM {table_name}             GROUP BY bowler, batsman             HAVING SUM(bowler_bowls_done) > 0             ORDER BY economy_rate ASC, bowler ASC, batsman ASC;",
    "exp": "This query calculates the total runs conceded by each bowler to each batsman, sums the total balls bowled by the bowler to that batsman, and computes the economy rate (runs conceded per over) for each bowler-batsman pair. The data is grouped by bowler and batsman, and results are ordered by economy rate in ascending order to highlight the most economical bowling performances against each batsman.",
    "variables": ["table_name"],
    "paraphrases": [
        "Calculate the economy rate for each bowler when bowling to every individual batsman.",
        "For every bowler-batsman encounter, what was the bowler's economy rate?",
        "List the bowling economy rate of each bowler against specific batsmen they bowled to."
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 94,
    "question": "Show number of no balls and wides bowled by each bowler to each batsman.",
    "query": "SELECT bowler, batsman, SUM(CASE WHEN runs LIKE '%nb%' THEN 1 ELSE 0 END) AS no_balls, SUM(CASE WHEN runs LIKE '%w%' THEN 1 ELSE 0 END) AS wides FROM {table_name} GROUP BY bowler, batsman ORDER BY no_balls DESC, wides DESC;",
    "exp": "This query counts the number of no-balls and wides bowled by each bowler to each batsman. It uses conditional aggregation to sum instances where the 'runs' column contains 'nb' for no-balls and 'w' for wides. The results are grouped by both bowler and batsman, then ordered first by descending no-ball counts and then wides, highlighting which bowler-batsman pairs had the most extras.",
    "variables": ["table_name"],
    "paraphrases": [
        "For every bowler-batsman matchup, how many no-balls and wides did the bowler deliver?",
        "List the total number of no-balls and wides bowled by each bowler to every batsman they faced.",
        "Provide a breakdown of no-balls and wides bowled by each bowler when bowling to specific batsmen."
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 95,
    "question": "Show total runs scored by each batsman against each bowler {temporal_phrase}.",
    "query": "SELECT               batsman,               bowler,               SUM(batsman_runs) AS total_runs             FROM {table_name}             WHERE {temporal_predicate}             GROUP BY batsman, bowler             ORDER BY total_runs DESC, batsman ASC, bowler ASC;",
    "exp": "This query calculates the total runs scored by each batsman against each bowler within the range of overs from x1 to x2. It groups the data by batsman and bowler and sums the runs scored by the batsman during that over range. The results are then ordered in descending order to show the highest scoring batsman-bowler pairs first.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many runs did each batsman score against each specific bowler {temporal_phrase}?",
        "List the total runs accumulated by every batsman against each bowler within the specified {temporal_phrase}.",
        "Provide a breakdown of runs scored by each batsman when facing specific bowlers {temporal_phrase}."
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 96,
    "question": "Show total wickets taken by each bowler against each batsman {temporal_phrase}.",
    "query": "SELECT               bowler,               batsman,               SUM(bowler_wickets) AS wickets_taken             FROM {table_name}             WHERE {temporal_predicate}             GROUP BY bowler, batsman             HAVING SUM(bowler_wickets) > 0             ORDER BY wickets_taken DESC, bowler ASC, batsman ASC;",
    "exp": "This query computes the number of wickets taken by each bowler against each batsman within a specified over range (from x1 to x2). It groups the records by bowler and batsman, sums the bowler_wickets in that interval, and orders the result in descending order of wickets taken to highlight the most successful matchups.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many wickets did each bowler take against each specific batsman {temporal_phrase}?",
        "List the total wickets claimed by every bowler against each batsman within the specified {temporal_phrase}.",
        "Provide a breakdown of wickets taken by each bowler when bowling to specific batsmen {temporal_phrase}."
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 97,
    "question": "Show number of dot balls bowled by each bowler to each batsman {temporal_phrase}.",
    "query": "SELECT               bowler,               batsman,               COUNT(*) AS dot_balls             FROM {table_name}             WHERE {temporal_predicate}             AND team_runs = 0             GROUP BY bowler, batsman             ORDER BY dot_balls DESC, bowler ASC, batsman ASC;",
    "exp": "This query calculates the number of dot balls (deliveries that resulted in zero team runs) bowled by each bowler to each batsman within a specified over range (from x1 to x2). It filters for zero-run deliveries, groups by bowler and batsman, counts the number of such deliveries, and sorts the result by the count in descending order to identify the most restrictive bowler-batsman matchups.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many dot balls did each bowler deliver to each specific batsman {temporal_phrase}?",
        "List the total number of dot balls bowled by every bowler to each batsman within the specified {temporal_phrase}.",
        "Provide a breakdown of dot balls bowled by each bowler when bowling to specific batsmen {temporal_phrase}."
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 98,
    "question": "Show number of sixes hit by each batsman against each bowler {temporal_phrase}.",
    "query": "SELECT               batsman,               bowler,               SUM(CASE WHEN batsman_runs = 6 THEN 1 ELSE 0 END) AS sixes_hit             FROM {table_name}             WHERE {temporal_predicate}             GROUP BY batsman, bowler             ORDER BY sixes_hit DESC, batsman ASC, bowler ASC;",
    "exp": "This query counts the number of sixes hit by each batsman off each bowler within a specified over range (from x1 to x2). It filters the data for the specified overs, uses a conditional sum to count only deliveries where the batsman scored 6 runs, groups the results by batsman and bowler, and orders the output by the number of sixes in descending order to highlight the most dominant matchups in terms of six-hitting.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "How many sixes did each batsman hit against each specific bowler {temporal_phrase}?",
        "List the total number of maximums scored by every batsman against each bowler within the specified {temporal_phrase}.",
        "Provide a breakdown of sixes hit by each batsman when facing specific bowlers {temporal_phrase}."
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 99,
    "question": "Show batting strike rate of each batsman against each bowler {temporal_phrase}.",
    "query": "WITH per_pair AS (               SELECT                 batsman,                 bowler,                 SUM(batsman_runs) AS total_runs,                 SUM(batsman_bowls_faced) AS balls_faced               FROM {table_name}               WHERE {temporal_predicate}               GROUP BY batsman, bowler               HAVING SUM(batsman_bowls_faced) > 0             ),             sr AS (               SELECT                 batsman,                 bowler,                 total_runs,                 balls_faced,                 (total_runs * 100.0) / NULLIF(balls_faced, 0) AS sr_exact,                 ROUND((total_runs * 100.0) / NULLIF(balls_faced, 0), 2) AS strike_rate               FROM per_pair             )             SELECT batsman, bowler, total_runs, balls_faced, strike_rate             FROM sr             ORDER BY sr_exact DESC, total_runs DESC, batsman ASC, bowler ASC;",
    "exp": "This query calculates the strike rate of each batsman against each bowler within a specified over range (from x1 to x2). It sums the total runs and balls faced by each batsman against each bowler, computes the strike rate as (runs / balls) * 100, and orders the result by strike rate in descending order to show the most aggressive matchups.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Calculate the strike rate for each batsman when facing every individual bowler {temporal_phrase}.",
        "For every batsman-bowler encounter within the {temporal_phrase}, what was the batsman's strike rate?",
        "List the batting strike rate of each batsman against specific bowlers they faced {temporal_phrase}."
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 100,
    "question": "Show economy rate of each bowler against each batsman {temporal_phrase}. Consider the extras and byes as runs given my bowler.",
    "query": "WITH per_pair AS (               SELECT                 bowler,                 batsman,                 SUM(team_runs) AS total_runs_conceded,                 SUM(bowler_bowls_done) AS balls_bowled               FROM {table_name}               WHERE {temporal_predicate}               GROUP BY bowler, batsman               HAVING SUM(bowler_bowls_done) > 0),             econ AS (               SELECT                 bowler,                 batsman,                 total_runs_conceded,                 balls_bowled,                 (total_runs_conceded * 6.0) / NULLIF(balls_bowled, 0) AS econ_exact,                 ROUND((total_runs_conceded * 6.0) / NULLIF(balls_bowled, 0), 2) AS economy_rate               FROM per_pair             )             SELECT bowler, batsman, total_runs_conceded, balls_bowled, economy_rate             FROM econ             ORDER BY econ_exact ASC, bowler ASC, batsman ASC;",
    "exp": "This query calculates the economy rate of each bowler against each batsman within a specific over range (from x1 to x2). It aggregates the total runs conceded and the number of legitimate balls bowled (i.e., excluding extras) by each bowler to each batsman. The economy rate is computed as (runs conceded * 6) / balls bowled, and the results are ordered by economy rate in ascending order to highlight the most economical matchups.",
    "variables": ["table_name", "temporal_phrase", "temporal_predicate"],
    "paraphrases": [
        "Calculate the economy rate for each bowler when bowling to every individual batsman {temporal_phrase}.",
        "For every bowler-batsman encounter within the {temporal_phrase}, what was the bowler's economy rate?",
        "List the bowling economy rate of each bowler against specific batsmen they bowled to {temporal_phrase}."
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 101,
    "question": "List all bowlers sorted by total runs conceded, with number of balls bowled and economy rate across all batsmen.",
    "query": "SELECT               bowler,               SUM(bowler_runs_given) AS total_runs_conceded,               SUM(bowler_bowls_done) AS balls_bowled,               ROUND((SUM(bowler_runs_given) * 6.0) / NULLIF(SUM(bowler_bowls_done), 0), 2) AS economy_rate             FROM {table_name}             GROUP BY bowler             ORDER BY total_runs_conceded DESC, bowler ASC;",
    "exp": "This query calculates the total runs conceded, total balls bowled, and economy rate for each bowler across the entire dataset. The economy rate is computed as (total runs conceded * 6) / total balls bowled, representing the average number of runs conceded per over. The results are sorted in descending order of total runs conceded to identify bowlers who have given away the most runs overall.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each bowler, show their total runs conceded, the number of balls they bowled, and their economy rate, ordered by runs conceded.",
        "List all bowlers by how many runs they gave up, along with their total balls bowled and economy rate.",
        "Display a ranking of bowlers based on runs conceded, including balls bowled and economy rate."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 102,
    "question": "Show how many runs each batsman scored against the bowler who conceded the most runs (including byes and extras).",
    "query": "WITH per_bowler AS (               SELECT bowler, SUM(team_runs) AS team_runs_conceded               FROM {table_name}               GROUP BY bowler             ),             top_bowlers AS (               SELECT bowler               FROM per_bowler               WHERE team_runs_conceded = (SELECT MAX(team_runs_conceded) FROM per_bowler)             )             SELECT               t.batsman,               t.bowler,               SUM(t.batsman_runs) AS total_runs             FROM {table_name} t             WHERE t.bowler IN (SELECT bowler FROM top_bowlers)             GROUP BY t.batsman, t.bowler             ORDER BY t.bowler ASC, total_runs DESC, t.batsman ASC;",
    "exp": "This query first identifies the bowler who has conceded the most runs overall using a Common Table Expression (CTE) named `top_bowler`. It then filters the dataset to only include deliveries bowled by this bowler and aggregates the runs scored by each batsman against them. The results show which batsmen have scored the most runs off the top run-conceding bowler, sorted in descending order of total runs.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the bowler who gave away the most runs, and then show the individual scores of each batsman against that bowler.",
        "For the most expensive bowler, list the total runs scored by each batsman against them.",
        "Which batsman scored the most runs off the bowler with the highest runs conceded?"
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 103,
    "question": "Show number of sixes hit by each batsman against the bowler who conceded the most runs.",
    "query": "WITH per_bowler AS (               SELECT bowler, SUM(bowler_runs_given) AS runs_conceded               FROM {table_name}               GROUP BY bowler             ),             top_bowlers AS (               SELECT bowler               FROM per_bowler               WHERE runs_conceded = (SELECT MAX(runs_conceded) FROM per_bowler)             )             SELECT               t.batsman,               t.bowler,               SUM(CASE WHEN t.batsman_runs = 6 THEN 1 ELSE 0 END) AS sixes_hit             FROM {table_name} t             WHERE t.bowler IN (SELECT bowler FROM top_bowlers)             GROUP BY t.batsman, t.bowler             ORDER BY t.bowler ASC, sixes_hit DESC, t.batsman ASC;",
    "exp": "This query identifies the bowler who has conceded the most total runs using a Common Table Expression (CTE) named `top_bowler`. It then filters the main table to include only deliveries bowled by that bowler and counts how many sixes each batsman has hit against them. The result lists batsmen in descending order based on the number of sixes hit off this most-expensive bowler.",
    "variables": ["table_name"],
    "paraphrases": [
        "Against the bowler who conceded the most runs, how many sixes did each batsman hit?",
        "For the bowler who was most expensive, list the number of sixes hit by each batsman.",
        "Which batsmen hit the most sixes off the bowler who gave away the most runs?"
    ],
    "primary_key": ["batsman", "bowler"]
    },
    {
    "id": 104,
    "question": "Show strike rate of each batsman against the bowler who conceded the most runs.",
    "query": "WITH per_bowler AS (               SELECT                 bowler,                 SUM(bowler_runs_given) AS runs_conceded               FROM {table_name}               GROUP BY bowler             ),             top_bowlers AS (               SELECT bowler               FROM per_bowler               WHERE runs_conceded = (SELECT MAX(runs_conceded) FROM per_bowler)             ),             per_pair AS (               SELECT                 t.batsman,                 t.bowler,                 SUM(t.batsman_runs) AS runs,                 SUM(t.batsman_bowls_faced) AS balls               FROM {table_name} t               WHERE t.bowler IN (SELECT bowler FROM top_bowlers)               GROUP BY t.batsman, t.bowler               HAVING SUM(t.batsman_bowls_faced) > 0             )             SELECT               bowler,               batsman,               ROUND(runs * 100.0 / NULLIF(balls, 0), 2) AS strike_rate             FROM per_pair             ORDER BY bowler ASC, strike_rate DESC, batsman ASC;",
    "exp": "First, the query identifies the bowler who conceded the most runs in the match by grouping by bowler and ordering by the sum of runs conceded. Then, for that bowler, it calculates for each batsman the total runs scored, total balls faced, and the strike rate (runs per 100 balls). Finally, it lists the batsmen facing that bowler ordered by their strike rate in descending order.",
    "variables": ["table_name"],
    "paraphrases": [
        "What was each batsman's strike rate against the bowler who conceded the most runs?",
        "For the bowler who was most expensive, calculate the strike rate of each batsman against them.",
        "Show the strike rate for batsmen when facing the bowler who gave up the most runs."
    ],
    "primary_key": ["bowler", "batsman"]
    },
    {
    "id": 105,
    "question": "Show the highest conceding over for each bowler.",
    "query": "WITH bowler_over_runs AS (              SELECT                 bowler,                 CEIL(overs) AS over_number,                 SUM(team_runs) AS runs_in_over               FROM {table_name}               WHERE overs IS NOT NULL               GROUP BY bowler, CEIL(overs)             ),             ranked_overs AS (               SELECT                 bowler, over_number, runs_in_over,                 RANK() OVER (PARTITION BY bowler ORDER BY runs_in_over DESC) AS over_rank               FROM bowler_over_runs             )             SELECT bowler, over_number, runs_in_over             FROM ranked_overs             WHERE over_rank = 1             ORDER BY runs_in_over DESC, bowler ASC, over_number ASC;",
    "exp": "The query first calculates the total runs each bowler conceded per over by grouping data by bowler and the integer part of overs (over number). Then, it ranks the overs for each bowler based on runs conceded in descending order. Finally, it selects the top-ranked over (the over with the most runs conceded) for each bowler and lists them ordered by runs conceded descending.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each bowler, identify the over in which they gave away the most runs, and show that over's run count.",
        "Which was the most expensive over bowled by each bowler?",
        "List each bowler's worst over (in terms of runs conceded) and the runs scored in that over."
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 106,
    "question": "Show the top 5 most expensive overs bowled by any bowler. (if ties return in order of over number and bowler names)",
    "query": "SELECT               bowler,               CEIL(overs) AS over_number,               SUM(team_runs) AS runs_in_over             FROM {table_name}             GROUP BY bowler, CEIL(overs)             ORDER BY runs_in_over DESC, over_number ASC, bowler ASC             LIMIT 5;",
    "exp": "This query calculates the total runs conceded by each bowler in each over by grouping the data by bowler and the integer part of the overs (which represents the over number). It then orders these results by the runs conceded in descending order to find the most expensive overs and limits the output to the top 5 overs with the highest runs conceded.",
    "variables": ["table_name"],
    "paraphrases": [
        "List the five overs where the most runs were conceded, indicating the bowler and the over number.(if ties return in order of over number and bowler names)",
        "What were the top 5 most expensive overs bowled in the match? (if ties return in order of over number and bowler names)",
        "Show the 5 overs with the highest runs conceded, along with the bowler for each. (if ties return in order of over number and bowler names)"
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 107,
    "question": "Which batsman had the highest strike rate (runs per 100 balls faced) in the match and what was the strike rate?",
    "query": "WITH per_batsman AS (               SELECT                 batsman,                 SUM(batsman_runs) AS runs,                 SUM(batsman_bowls_faced) AS balls               FROM {table_name}               GROUP BY batsman               HAVING SUM(batsman_bowls_faced) > 0             ),             sr AS (               SELECT                 batsman,                 (runs * 100.0) / NULLIF(balls, 0) AS sr_exact,                 ROUND((runs * 100.0) / NULLIF(balls, 0), 2) AS strike_rate               FROM per_batsman             ),             best AS (SELECT MAX(sr_exact) AS max_sr FROM sr)             SELECT batsman, strike_rate             FROM sr             WHERE sr_exact = (SELECT max_sr FROM best);",
    "exp": "This query calculates the strike rate for each batsman by dividing the total runs scored by the total balls faced and multiplying by 100. The result is rounded to two decimal places. It then orders the batsmen by their strike rate in descending order and returns the top batsman with the highest strike rate.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the batsman with the best strike rate in the entire match and their strike rate value.",
        "Who had the highest runs per 100 balls faced, and what was that rate?",
        "Find the batsman with the highest strike rate in the game and show their strike rate."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 108,
    "question": "Find the bowler with the best economy rate (runs per over) among those who bowled at least 3 overs.",
    "query": "WITH per_bowler AS (               SELECT                 bowler,                 SUM(bowler_runs_given) AS runs_conceded,                 SUM(bowler_bowls_done) AS balls_bowled               FROM {table_name}               GROUP BY bowler               HAVING SUM(bowler_bowls_done) >= 18             ),             econ AS (               SELECT                 bowler,                 (runs_conceded * 6.0) / NULLIF(balls_bowled, 0) AS econ_exact,                 ROUND((runs_conceded * 6.0) / NULLIF(balls_bowled, 0), 2) AS economy_rate               FROM per_bowler             ),             best AS (               SELECT MIN(econ_exact) AS best_econ FROM econ             )             SELECT bowler, economy_rate             FROM econ             WHERE econ_exact = (SELECT best_econ FROM best);",
    "exp": "This query calculates the economy rate for each bowler, which is the average number of runs conceded per over. It sums the total runs given and divides it by the total number of overs bowled (balls bowled divided by 6). Only bowlers who have bowled at least 18 balls (3 overs) are considered. The bowlers are then ordered by their economy rate in ascending order, and the bowler with the lowest economy rate is returned.",
    "variables": ["table_name"],
    "paraphrases": [
        "Among bowlers who completed at least 3 overs, who has the best economy rate, and what is it?",
        "Identify the most economical bowler (runs per over) who bowled a minimum of 18 balls.",
        "Which bowler, having bowled at least 3 overs, has the lowest economy rate?"
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 109,
    "question": "Which over saw the highest total number of runs scored in the match, and how many runs were scored in that over?",
    "query": "WITH over_totals AS (               SELECT                 CEIL(overs) AS over_number,                 SUM(team_runs) AS total_runs               FROM {table_name}               GROUP BY CEIL(overs)             ),             mx AS (SELECT MAX(total_runs) AS max_runs FROM over_totals)             SELECT over_number, total_runs             FROM over_totals             WHERE total_runs = (SELECT max_runs FROM mx);",
    "exp": "It groups the data by the integer part of the over number (using FLOOR to treat balls within an over as one group), sums the total runs scored in each over, and then orders the overs by total runs scored in descending order. Finally, it returns the over with the maximum total runs.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the over with the most runs scored in the entire match and state the run total.",
        "Which over had the highest number of runs, and what was that score?",
        "Find the highest-scoring over in the game and how many runs it contained."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 110,
    "question": "Which batsman scored the fastest 20 runs (in the fewest balls faced)?",
    "query": "WITH seq AS (               SELECT                 batsman,                 overs,                 SUM(batsman_runs) OVER (                   PARTITION BY batsman                   ORDER BY overs                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW                 ) AS cum_runs,                 SUM(CASE WHEN runs NOT LIKE '%w%' THEN 1 ELSE 0 END) OVER (                   PARTITION BY batsman                   ORDER BY overs                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW                 ) AS cum_balls               FROM {table_name}             ),             first_hit AS (               SELECT batsman, MIN(cum_balls) AS balls_to_20               FROM seq               WHERE cum_runs >= 20               GROUP BY batsman             ),             best AS (SELECT MIN(balls_to_20) AS min_balls FROM first_hit)             SELECT batsman, balls_to_20 AS balls_taken             FROM first_hit             WHERE balls_to_20 = (SELECT min_balls FROM best);",
    "exp": "This query finds the batsman who scored at least 20 runs with the fewest balls faced. First, it calculates total runs and balls faced per batsman, filtering only those with 30 or more runs. Then, it selects the minimum ball count among these batsmen to identify the most efficient scorer who reached or exceeded 30 runs in the least number of balls.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the batsman who reached 20 runs in the fewest deliveries, and how many balls they took.",
        "Who was the quickest to score 20 runs in terms of balls faced?",
        "Find the batsman who scored 20 runs with the lowest number of balls faced."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 111,
    "question": "What is the percentage of dot balls bowled by {bowler}?",
    "query": "SELECT               ROUND(                 100.0 * SUM(CASE WHEN team_runs = 0 THEN 1 ELSE 0 END)                 / COUNT(*),                 2               ) AS dot_ball_percentage             FROM {table_name}             WHERE bowler = '{bowler}'               AND runs NOT LIKE '%w%'               AND runs NOT LIKE '%nb%';",
    "exp": "This query calculates the percentage of dot balls bowled by the specified bowler. It counts the number of deliveries where no runs were scored (team_runs = 0) and divides it by the total number of deliveries bowled by that bowler, then multiplies by 100 to get a percentage, rounded to two decimal places.",
    "variables": ["table_name", "bowler"],
    "paraphrases": [
        "Calculate the percentage of deliveries bowled by {bowler} that resulted in no runs.",
        "Show the dot ball percentage for bowler {bowler}.",
        "What proportion of {bowler}'s balls were dot balls?"
    ],
    "primary_key": ["N/A"]
    },
    {
    "id": 112,
    "question": "Which batsman had the highest 6 percentage (percentage of balls faced that resulted in a six)?",
    "query": "WITH per_batter AS (               SELECT                 batsman,                 SUM(CASE WHEN batsman_runs = 6 THEN 1 ELSE 0 END) AS six_balls,                 COUNT(*) AS balls_faced               FROM {table_name}               WHERE runs NOT LIKE '%w%' AND runs NOT LIKE '%nb%'               GROUP BY batsman               HAVING COUNT(*) > 0             ),             pct AS (               SELECT                 batsman,                 100.0 * six_balls / NULLIF(balls_faced, 0) AS pct_exact,                 ROUND(100.0 * six_balls / NULLIF(balls_faced, 0), 2) AS six_percentage               FROM per_batter             )             SELECT batsman, six_percentage             FROM pct             WHERE pct_exact = (SELECT MAX(pct_exact) FROM pct);",
    "exp": "This query calculates the percentage of deliveries faced by each batsman that resulted in boundaries (either fours or sixes). It counts how many balls resulted in a boundary and divides by the total balls faced by that batsman, multiplies by 100, and rounds the result to two decimal places. The batsman with the highest boundary percentage is returned.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the batsman who hit the most sixes as a percentage of balls faced.",
        "Who has the highest percentage of balls faced that were boundaries (6s)?",
        "Find the batsman with the highest boundary percentage (6s) and their rate."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 113,
    "question": "Identify the over in which {batsman} scored the most runs and how many runs batsman scored in that over.",
    "query": "WITH over_runs AS (               SELECT                 CEIL(overs) AS over_number,                 SUM(batsman_runs) AS runs_in_over               FROM {table_name}               WHERE batsman = '{batsman}'               GROUP BY CEIL(overs)             ),             mx AS (SELECT MAX(runs_in_over) AS max_runs FROM over_runs)             SELECT over_number, runs_in_over             FROM over_runs             WHERE runs_in_over = (SELECT max_runs FROM mx);",
    "exp": "This query finds the over in which the specified batsman scored the most runs. It groups the data by each ball's over, sums the runs scored by the batsman in each over, orders the overs by total runs scored in descending order, and returns the over with the highest runs.",
    "variables": ["table_name", "batsman"],
    "paraphrases": [
        "Which over was {batsman}'s highest-scoring over, and what was the total runs scored in that over?",
        "For batsman {batsman}, find the over where they scored the most runs and show the runs scored in that over.",
        "In which over did {batsman} score their highest number of runs and show the runs scored in that over?"
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 114,
    "question": "Which batsman scored the highest percentage of their runs in boundaries (fours and sixes combined)?",
    "query": "WITH per_batter AS (               SELECT                 batsman,                 SUM(CASE WHEN batsman_runs IN (4,6) THEN batsman_runs ELSE 0 END) AS boundary_runs,                 SUM(batsman_runs) AS total_runs               FROM {table_name}               GROUP BY batsman               HAVING SUM(batsman_runs) > 0             ),             pct AS (               SELECT                 batsman,                 100.0 * boundary_runs / total_runs AS pct_exact,                 ROUND(100.0 * boundary_runs / total_runs, 2) AS boundary_run_percentage               FROM per_batter             )             SELECT batsman, boundary_run_percentage             FROM pct             WHERE pct_exact = (SELECT MAX(pct_exact) FROM pct);",
    "exp": "This query calculates the percentage of runs scored by each batsman through boundaries (fours and sixes). For each batsman, it sums the runs scored from boundaries (4s and 6s) and divides by their total runs scored, multiplying by 100 to get a percentage. It orders the batsmen by this percentage in descending order and returns the batsman with the highest boundary run percentage.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the batsman who got the largest proportion of their runs from fours and sixes.",
        "Who scored the highest percentage of their total runs through boundaries (4s + 6s)?",
        "Find the batsman with the highest boundary (4 or 6) run percentage and their rate."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 115,
    "question": "Who was the most expensive bowler (count extras and byes) in a single over and how many runs were conceded in that over?",
    "query": "WITH over_cost AS (               SELECT                 bowler,                 CEIL(overs) AS over_number,                 SUM(team_runs) AS runs_in_over               FROM {table_name}               GROUP BY bowler, CEIL(overs)             ),             mx AS (               SELECT MAX(runs_in_over) AS max_runs FROM over_cost             )             SELECT bowler, over_number, runs_in_over             FROM over_cost             WHERE runs_in_over = (SELECT max_runs FROM mx);",
    "exp": "This query finds the over in which a bowler conceded the most runs in the match. It groups data by bowler and the integer part of the overs (representing the over number), sums the runs conceded by the bowler in each over, then orders the results by runs conceded in descending order, returning the single over with the highest runs conceded.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the bowler and over where the most runs were given away (count extras and byes), and state the total runs conceded in that over.",
        "Which bowler had the most expensive single over, and what was the run count for that over?",
        "Find the bowler and over with the highest runs conceded in that over."
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 116,
    "question": "Which batsman had the highest average runs per over they batted in?",
    "query": "WITH per_batter AS (               SELECT                 batsman,                 SUM(batsman_runs) AS total_runs,                 COUNT(DISTINCT CEIL(overs)) AS overs_batted               FROM {table_name}               WHERE overs IS NOT NULL               GROUP BY batsman             ),             avg_table AS (               SELECT                 batsman,                 (total_runs * 1.0) / NULLIF(overs_batted, 0) AS avg_runs_per_over_exact,                 ROUND((total_runs * 1.0) / NULLIF(overs_batted, 0), 2) AS avg_runs_per_over               FROM per_batter             )             SELECT batsman, avg_runs_per_over             FROM avg_table             WHERE avg_runs_per_over_exact = (SELECT MAX(avg_runs_per_over_exact) FROM avg_table);",
    "exp": "This query calculates the average runs scored per over by each batsman across the match. It sums the total runs each batsman scored and divides it by the number of distinct overs they played in (counting each over only once). The result is rounded to two decimal places. Finally, it orders the batsmen by this average in descending order and returns the batsman with the highest average runs per over.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the batsman who scored the most runs on average for each over they were batting in.",
        "Who had the highest average runs per over batted, and what was that average?",
        "Find the batsman with the best average runs per over they faced and display it."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 117,
    "question": "Find all batsmen who hit more than 1 sixes and how many total runs they scored.",
    "query": "SELECT batsman, SUM(batsman_runs) AS total_runs, SUM(batsman_sixes) AS total_sixes FROM {table_name} GROUP BY batsman HAVING SUM(batsman_sixes) > 1 ORDER BY total_runs DESC;",
    "exp": "This query retrieves all batsmen who have hit more than one six in the match. It groups the data by each batsman, calculating the total runs and total sixes they scored. Only those batsmen with more than one six are included, and the results are ordered by total runs scored in descending order.",
    "variables": ["table_name"],
    "paraphrases": [
        "List all batsmen who hit more than one six, and show their total runs scored.",
        "Which batsmen hit at least two sixes, and what were their total runs?",
        "Show batsmen who hit more than one six, along with their aggregate runs."
    ],
    "primary_key": ["batsman"]
    },
    {
    "id": 118,
    "question": "Find bowlers who conceded more than 15 runs in any over.",
    "query": "SELECT bowler, Ceil(overs) AS over_number, SUM(team_runs) AS runs_in_over FROM {table_name} GROUP BY bowler, Ceil(overs) HAVING SUM(team_runs) > 15 ORDER BY runs_in_over DESC;",
    "explanation": "This query identifies overs where bowlers conceded more than 15 runs. It groups deliveries by bowler and the integer part of the over number (representing each over), sums the runs conceded in those overs, and filters to keep only overs with total runs greater than 15. The results are then sorted in descending order of runs conceded in each over.",
    "variables": ["table_name"],
    "paraphrases": [
        "List all bowlers who gave away more than 15 runs in any single over, indicating the over and runs.",
        "Identify the overs where a bowler conceded over 15 runs and specify the bowler and over number.",
        "Which bowlers had an over where they leaked more than 15 runs?"
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 119,
    "question": "Show the total number of dot balls bowled by each bowler.",
    "query": "SELECT bowler, COUNT(*) AS total_dot_balls FROM {table_name} WHERE team_runs = 0 GROUP BY bowler ORDER BY total_dot_balls DESC;",
    "exp": "It filters deliveries with zero team runs, groups them by bowler, counts the dot balls per bowler, and orders the bowlers by their dot ball count in descending order.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each bowler, count the total number of dot balls they delivered.",
        "How many dot balls did each bowler bowl in the match?",
        "List the total dot balls bowled by every bowler."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 120,
    "question": "Find the number of no-balls and total runs scored on them for each over.",
    "query": "SELECT Ceil(overs) AS over_number, COUNT(*) AS no_balls_delivered, SUM(team_runs) AS runs_off_no_balls FROM {table_name} WHERE runs LIKE '%nb%' GROUP BY Ceil(overs) ORDER BY over_number;",
    "exp": "This query calculates, for each over (using the floor value of overs), the total number of no-ball deliveries and the total runs scored off those no-balls. It filters rows where the runs field contains 'nb', groups the data by over number, and orders the results by the over number in ascending order.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each over, show the count of no-balls bowled and the total runs scored from those no-balls.",
        "How many no-balls were bowled in each over, and what runs resulted from them?",
        "List the number of no-balls and runs off no-balls for every over."
    ],
    "primary_key": ["over_number"]
    },
    {
    "id": 121,
    "question": "Which bowler bowled the most dot balls in the match?",
    "query": "WITH bowler_dots AS (               SELECT bowler, COUNT(*) AS total_dot_balls               FROM {table_name}               WHERE team_runs = 0               GROUP BY bowler             )             SELECT bowler, total_dot_balls             FROM bowler_dots             WHERE total_dot_balls = (SELECT MAX(total_dot_balls) FROM bowler_dots);",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the bowlers who delivered the highest number of dot balls in the entire match.",
        "Which bowlers had the most dot balls to their name?",
        "Show the bowlers with the highest total of dot balls."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 122,
    "question": "Which bowler conceded the most no-balls and how many runs came off them?",
    "query": "WITH bowler_nb AS (               SELECT bowler,                     COUNT(*) AS no_balls_delivered,                     SUM(team_runs) AS runs_off_no_balls               FROM {table_name}               WHERE runs LIKE '%nb%'               GROUP BY bowler             )             SELECT bowler, no_balls_delivered, runs_off_no_balls             FROM bowler_nb             WHERE no_balls_delivered = (               SELECT MAX(no_balls_delivered) FROM bowler_nb);",
    "exp": "This query identifies each bowler's number of no-ball deliveries by counting rows where the runs field contains 'nb'. It also sums the total runs scored off these no-balls. The results are grouped by bowler and ordered descending by runs scored off no-balls.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the bowlers who bowled the most no-balls and the total runs that resulted from those no-balls.",
        "Which bowlers gave away the most no-balls, and how many runs did they concede through them?",
        "Show the bowlers with the highest number of no-balls and the runs scored off them."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 123,
    "question": "Which bowler conceded the most wides and how many wides did the bowler bowl?",
    "query": "WITH bowler_wides AS (               SELECT bowler, COUNT(*) AS wides_delivered               FROM {table_name}               WHERE runs LIKE '%w%'               GROUP BY bowler             )             SELECT bowler, wides_delivered             FROM bowler_wides             WHERE wides_delivered = (             SELECT MAX(wides_delivered) FROM bowler_wides);",
    "explanation": "This query counts the total number of wides delivered by each bowler by filtering rows where the runs column contains 'w'. It groups the data by bowler and orders the results in descending order to show which bowler has bowled the most wides.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify the bowlers who delivered the highest number of wide balls.",
        "Which bowlers bowled the most wides in the match?",
        "Show the bowlers with the highest count of wide deliveries."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 124,
    "question": "In which overs did each bowler concede more than 6 runs?",
    "query": "SELECT bowler, Ceil(overs) AS over_number, SUM(team_runs) AS runs_in_over FROM {table_name} GROUP BY bowler, Ceil(overs) HAVING SUM(team_runs) > 6 ORDER BY runs_in_over DESC;",
    "explanation": "This query calculates the total runs conceded by each bowler in each over by grouping the data by bowler and the floored over number. It filters to include only those overs where the bowler conceded more than 6 runs. The results are then ordered in descending order of runs conceded to identify the most expensive overs.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each bowler, list the overs in which they conceded more than 6 runs, along with the run count.",
        "Identify the overs where individual bowlers gave away over 6 runs, specifying the bowler, over and run count.",
        "Show all bowlers, overs and runs conceeded in that over where a bowler conceded more than 6 runs."
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 125,
    "question": "Which bowlers took wickets and how many wickets did they take ? How many runs did they concede?",
    "query": "SELECT             bowler,             SUM(CASE WHEN bowler_wickets > 0 THEN bowler_wickets ELSE 0 END) AS total_wickets,             SUM(bowler_runs_given) AS runs_conceded             FROM {table_name}             GROUP BY bowler             HAVING SUM(CASE WHEN bowler_wickets > 0 THEN bowler_wickets ELSE 0 END) > 0             ORDER BY total_wickets DESC, runs_conceded ASC;",
    "exp": "This query selects each bowler who has taken at least one wicket. For each such bowler, it sums up the total wickets taken and the total runs conceded. The results are grouped by bowler and ordered primarily by the highest number of wickets taken in descending order, and secondarily by the fewest runs conceded in ascending order to highlight the most effective wicket-taking bowlers with economical bowling.",
    "variables": ["table_name"],
    "paraphrases": [
        "For each bowler who took at least one wicket, show their total wickets and total runs conceded.",
        "List bowlers who claimed wickets, along with the number of wickets taken and runs given away.",
        "Show wicket-taking bowlers, their total wickets, and their total runs conceded."
    ],
    "primary_key": ["bowler"]
    },
    {
    "id": 126,
    "question": "Which bowlers had an over where they conceded a six or a four or a no-ball, and how many runs did they concede in that over?",
    "query": "SELECT bowler, Ceil(overs) AS over_number, SUM(team_runs) AS total_runs_in_over FROM {table_name} GROUP BY bowler, Ceil(overs) HAVING SUM(batsman_sixes) >= 1 OR SUM(batsman_fours) >= 1 OR SUM(CASE WHEN runs LIKE '%nb%' THEN 1 ELSE 0 END) >= 1 ORDER BY total_runs_in_over DESC;",
    "exp": "This query retrieves all overs bowled by each bowler where impactful events occurred—specifically, at least one six, one four, or one no-ball was delivered. It groups the data by bowler and over, calculates the total runs conceded in that over, and filters to include only those overs where at least one of the specified conditions is met. The result is ordered by total runs in descending order to highlight the most expensive overs with high-impact deliveries.",
    "variables": ["table_name"],
    "paraphrases": [
        "Identify overs where a bowler bowled either a six, a four, or a no-ball, and show the total runs conceded in that over.",
        "For each bowler, list any over in which they conceded a boundary (4 or 6) or a no-ball, along with the runs conceded in that over.",
        "Show overs where a bowler gave away a four, a six, or a no-ball, and the total runs in that over."
    ],
    "primary_key": ["bowler", "over_number"]
    },
    {
    "id": 127,
    "question": "For each bowler, find their best and worst over by runs conceded (including byes and extras) and show the difference.",
    "query": "WITH bowler_over_summary AS (     SELECT bowler, Ceil(overs) AS over_number, SUM(team_runs) AS runs_in_over     FROM {table_name}     GROUP BY bowler, Ceil(overs) ), min_max_runs AS (     SELECT bowler, MIN(runs_in_over) AS best_over_runs, MAX(runs_in_over) AS worst_over_runs     FROM bowler_over_summary     GROUP BY bowler ) SELECT bowler, best_over_runs, worst_over_runs, (worst_over_runs - best_over_runs) AS run_difference FROM min_max_runs ORDER BY run_difference DESC;",
    "exp": "This query calculates the variability in performance for each bowler across overs. First, it computes the total runs conceded by each bowler per over (`bowler_over_summary`). Then, for each bowler, it finds their best (minimum) and worst (maximum) over in terms of runs conceded (`min_max_runs`). Finally, it computes the difference between their worst and best over (`run_difference`) to assess consistency or volatility, and orders the results in descending order of this difference.",
    "variables": ["table_name"],
    "paraphrases": [
        "For every bowler, show the runs conceded in their best (least expensive) and worst (most expensive) over, and the difference between these two figures.",
        "Identify each bowler's most and least expensive overs in terms of runs for every bowler, and calculate the run differential.",
        "List each bowler's best and worst over by runs conceded, and the gap between them."
    ],
    "primary_key": ["bowler"]
    },
    {
        "id": 128,
        "query":"SELECT \n    CASE WHEN wickets_in_over > 0 THEN 'Wicket Over' ELSE 'Non-Wicket Over' END AS over_type,\n    AVG(batsman_runs) AS average_batsman_runs\nFROM (\n    SELECT \n        overs,\n        batsman_runs,\n        SUM(bowler_wickets) OVER (PARTITION BY CEIL(overs)) AS wickets_in_over\n    FROM {table_name}\n) AS sub\nGROUP BY over_type;",
        "exp": "This query calculates the average runs scored by batsmen in overs where at least one wicket was taken, and compares it to the overall average batsman runs. It uses a subquery and a CASE expression to identify wicket-taking overs and non-wicket-taking overs, then groups the data by over type and calculates the average runs for each group.",
        "variables": ["table_name"],
        "question": "Compare the average runs scored by batsmen in overs with wickets versus overs without wickets.",
        "paraphrases": [
            "Compare the average runs scored by batsmen in overs with wickets versus overs without wickets.",
            "How do average runs scored by batsmen differ between overs with wickets and overs without wickets?",
            "What is the average of batsman runs for 'Wicket Over' types versus 'Non-Wicket Over' types?"
        ],
        "primary_key": ["over_type"]
    }    
]