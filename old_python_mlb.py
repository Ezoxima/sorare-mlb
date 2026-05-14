import requests
import json
import time
import ast
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from gspread_dataframe import set_with_dataframe

API_URL="https://api.sorare.com/federation/graphql"
API_KEY="26c64555091c246b534fb6f587cff8704f9ca5436d1119c1a06facc84da34d29f96f238caaedbe319137058aef7890c26ea44de7800062c2b2e45c30326sr128"

headers = {
    "Content-Type": "application/json",
    "APIKEY": API_KEY
}


def maj_gw_infos(type_gw):

    ## APPEL API ##
    query = f"""
            {{
              so5 {{
                featuredSo5Fixtures(sport: BASEBALL first: 1000 eventType: {type_gw}) {{
                  gameWeek
                  id
                  slug
                  canCompose
                  cutOffDate
                  endDate
                }}
              }}
            }}
            """
    
    response = requests.post("https://api.sorare.com/federation/graphql", json={'query': query}, headers=headers)
    data = json.loads(response.text)    
    
    df = pd.json_normalize(data['data']['so5']['featuredSo5Fixtures'])   

    df = df.rename(columns={
      'gameWeek': 'gw_int',
      'id': 'gw_id',
      'slug': 'gw_slug',
      'canCompose': 'gw_upcoming',
      'cutOffDate': 'gw_begin_date',
      'endDate': 'gw_end_date'
    })
    
    df = df[['gw_id', 'gw_int', 'gw_slug', 'gw_upcoming', 'gw_begin_date', 'gw_end_date']]

    # Conversion des dates #
    df['gw_begin_date'] = pd.to_datetime(df['gw_begin_date']).dt.strftime('%Y-%m-%d %H:%M:%S')
    df['gw_end_date'] = pd.to_datetime(df['gw_end_date']).dt.strftime('%Y-%m-%d %H:%M:%S')

    # Travail sur l'id de la GW, pour ne plus avoir le "So5Fixture:" devant #
    df['gw_id'] = df['gw_id'].apply(lambda x: x.split(":")[1])

    return df

def get_teams(): 

	query = """
			{
				teams(sport: BASEBALL) {
					nodes {
						slug
					}
				}
			}
			"""

	headers = {
		"Content-Type": "application/json",
		"APIKEY": API_KEY
	}

	response = requests.post(API_URL, json={'query': query}, headers=headers)
	data = json.loads(response.text)

	data = data['data']['teams']['nodes']
	df = pd.json_normalize(data)

	return df


def get_players_by_team(df):


	list_club = df['slug'].to_list()
	data_total = []
	# total_clubs = len(list_club)

	for i, club in enumerate(list_club):

		# clubs_restants = total_clubs - (i + 1)
		# print(f"{club} : {clubs_restants} clubs restants")

		hasNextPage = True
		endCursor = ""
		
		while hasNextPage:

			query = f"""
					{{
						team(slug: "{club}") {{
							name
							activePlayers(after: "{endCursor}") {{
								nodes {{
									slug
								}}
								pageInfo {{
									hasNextPage
									endCursor
								}}
							}}   
						}}
					}}
					"""

			response = requests.post(API_URL, json={'query': query}, headers=headers)
			data = json.loads(response.text)   

			team_name = data['data']['team']['name']
			players = data['data']['team']['activePlayers']['nodes']

			# Ajoute le nom de la team à chaque joueur
			for player in players:
				player['teamName'] = team_name
				data_total.append(player)

			hasNextPage = data['data']['team']['activePlayers']['pageInfo']['hasNextPage']
			endCursor = data['data']['team']['activePlayers']['pageInfo']['endCursor']

	df_players = pd.json_normalize(data_total)

	return df_players
							



def get_infos_players(df_players):

	list_players = df_players['slug'].to_list()
	players_with_infos = []
	# total_players = len(list_players)

	for i, player in enumerate(list_players):

		# joueurs_restants = total_players - (i + 1)
		# print(f"{player} : {joueurs_restants} joueurs restants")

		query = f"""
				{{
					anyPlayer(slug: "{player}") {{
						... on BaseballPlayer {{
							slug
							displayName
							age
							activeClub {{
								name
							}}
							country {{
								name
							}}
							batHand
							anyPositions
							cardPositions
							appearances
							seasonAppearances
							shirtNumber
							cardPrice(rarity: common)
							injuries {{
								active
								details
								expectedEndDate
								kind
								status
							}}     
							averageScore(type: SEASON_AVERAGE_SCORE)
						}}
					}}
				}}"""
		
		response = requests.post(API_URL, json={'query': query}, headers=headers)
		data = json.loads(response.text)

		player_data = data['data']['anyPlayer']

		active_injury, localisation_injury, details_injury, endDate_injury, ILL_injury = "", "", "", "", ""
		if player_data['injuries'] != []:
			active_injury = player_data['injuries'][0]['active']
			localisation_injury = player_data['injuries'][0]['kind']
			details_injury = player_data['injuries'][0]['details']
			endDate_injury = player_data['injuries'][0]['expectedEndDate']
			ILL_injury = player_data['injuries'][0]['status']	

		card_price = ""
		if player_data['cardPrice'] is not None:
			card_price = player_data['cardPrice']

		AverageScore = ""
		if player_data['averageScore'] is not None:	
			AverageScore = player_data['averageScore']

		players_with_infos.append({
			"slug": player_data['slug'],
			"Name": player_data['displayName'],
			"Age": player_data['age'],
			"Club": player_data['activeClub']['name'] if player_data['activeClub'] else None,
			"Country": player_data['country']['name'] if player_data['country'] else None,
			"BatHand": player_data['batHand'],
			"SeasonAppearances": player_data['seasonAppearances'],
			"CardPrice": card_price,
			"Active_injury": active_injury,
			"Localisation_injury": localisation_injury,
			"Details_injury": details_injury,
			"EndDate_injury": endDate_injury,
			"ILL_injury": ILL_injury,
			"AverageScore": AverageScore
		})

	df_players_infos = pd.DataFrame(players_with_infos)

	return df_players_infos

def convert_currency_to_eur(value, currency):
    """
    Convertit une valeur d'une devise donnée en euros.
    """
    if currency == "eur":
        return value

    # Exemple de taux statiques (à remplacer par un appel d'API en réel)
    rates = {
        "usd": 0.87,
        "gbp": 1.15,
        "eth": 1774.62
    }

    if currency in rates:
        result = value * rates[currency] 
        return result
    
    return None


def get_price_in_eur_from_amounts(amounts):
    """
    Essaie de lire les différentes monnaies dans un ordre de priorité et convertir en EUR.
    """
    if not amounts:
        return None

    if 'eurCents' in amounts and amounts['eurCents']:
        return amounts['eurCents'] / 100

    if 'usdCents' in amounts and amounts['usdCents']:
        return convert_currency_to_eur(amounts['usdCents'] / 100, 'usd')

    if 'gbpCents' in amounts and amounts['gbpCents']:
        return convert_currency_to_eur(amounts['gbpCents'] / 100, 'gbp')

    if 'wei' in amounts and amounts['wei']:
        try:
            eth_amount = int(amounts['wei']) / 1e18  # conversion WEI -> ETH
            return convert_currency_to_eur(eth_amount, 'eth')
        except:
            return None

    return None


def get_lowest_prices_players(df_players):

	list_players = df_players['slug'].to_list()
	players_price = []
	total_players = len(list_players)

	for i, player in enumerate(list_players):
		joueurs_restants = total_players - (i + 1)
		print(f"{player} : {joueurs_restants} joueurs restants")

		# Initialise un dictionnaire vide avec slug + colonnes de rareté à None
		player_info = {
			"slug": player,
			"Lowest_limited_Price": None,
			"Lowest_rare_Price": None
		}

		rarities = ['limited', 'rare', 'super_rare', 'unique']
		in_seasons = ["true", "false"]

		for rarity in rarities:

			for in_season in in_seasons:

				query = f"""
				{{
					anyPlayer(slug: "{player}") {{
						... on BaseballPlayer {{
							slug
							lowestPriceAnyCard(inSeason: {in_season} rarity: {rarity}) {{
								slug
                                name
								sealableFor
								liveSingleSaleOffer {{								
									receiverSide {{
										amounts {{
											eurCents
											gbpCents
											usdCents
											wei
										}}
									}}
								}}
								latestPrimaryOffer{{
									price {{
										eurCents
										gbpCents
										usdCents
										wei
									}}
								}}
							}}
						}}
					}}
				}}"""
				
				response = requests.post(API_URL, json={'query': query}, headers=headers)
				data = json.loads(response.text)

				player_data = data['data']['anyPlayer']

				# Vérifie si le prix existe
				try:
					amounts = player_data['lowestPriceAnyCard']['liveSingleSaleOffer']['receiverSide']['amounts']
					price = get_price_in_eur_from_amounts(amounts)
				except:
					try:
						amounts = player_data['lowestPriceAnyCard']['latestPrimaryOffer']['price']
						price = get_price_in_eur_from_amounts(amounts)
					except:
						price = None

				# Ajoute le prix à la bonne colonne
				player_info[f"Lowest_{rarity}_IS_{in_season}_Price"] = price

			players_price.append(player_info)

	df_players_prices = pd.DataFrame(players_price).drop_duplicates()

	return df_players_prices


# Récupération des postes des joueurs

df_players_positions = pd.read_csv('data.csv', usecols=['slug', 'anyPositions', 'seasonYear'])
df_players_positions['slug'] = df_players_positions['slug'].str.extract(r'^((?:.*?)-\d{8})')
df_players_positions = df_players_positions.groupby(['slug', 'anyPositions', 'seasonYear']).size().reset_index(name='count')

df_players_positions['anyPositions'] = df_players_positions['anyPositions'].apply(ast.literal_eval)
positions_df = df_players_positions['anyPositions'].apply(pd.Series)
positions_df.columns = [f'position_{i+1}' for i in range(positions_df.shape[1])]

df_players_positions = pd.concat([df_players_positions.drop(columns=['anyPositions']), positions_df], axis=1)

map_exact = dict(zip(poste_mlb['position'], poste_mlb['exact_position']))
map_agg = dict(zip(poste_mlb['position'], poste_mlb['agg_position']))
position_cols = [col for col in df_players_positions.columns if col.startswith('position_')]

for col in position_cols:
    df_players_positions[col] = df_players_positions[col].map(map_exact)
    
for col in position_cols:
    agg_col = f'agg_{col}'
    df_players_positions[agg_col] = df_players_positions[col].map(lambda x: poste_mlb.loc[poste_mlb['exact_position'] == x, 'agg_position'].values[0] if pd.notnull(x) else None)
    
# Supprimer doublons dans agg_position_* colonnes ligne par ligne
agg_cols = [f'agg_{col}' for col in position_cols]

def remove_duplicates(row):
    seen = set()
    for col in agg_cols:
        val = row[col]
        if val in seen:
            row[col] = None
        elif val is not None:
            seen.add(val)
    return row

df_players_positions = df_players_positions.apply(remove_duplicates, axis=1)

agg_cols = [col for col in df_players_positions.columns if col.startswith('agg_position_')]

def shift_left(row):
    values = [row[col] for col in agg_cols if pd.notna(row[col]) and row[col] is not None]
    values += [None] * (len(agg_cols) - len(values))
    for i, col in enumerate(agg_cols):
        row[col] = values[i]
    return row

df_players_positions = df_players_positions.apply(shift_left, axis=1)
df_players_positions = df_players_positions.dropna(axis=1, how='all').where(pd.notna(df_players_positions), None)

df_players_positions.to_csv('data_players_pos_mlb.csv', index=False, sep=';')

df_players_pos_2025 = df_players_positions.loc[
    df_players_positions['seasonYear'] == 2025,
    ['slug', 'count', 'agg_position_1', 'agg_position_2', 'agg_position_3']
]

cols = ['agg_position_1', 'agg_position_2', 'agg_position_3']
df_players_pos_2025['non_null_count'] = df_players_pos_2025[cols].notnull().sum(axis=1)
best_rows_idx = df_players_pos_2025.groupby('slug')['non_null_count'].idxmax()
df_best_positions = df_players_pos_2025.loc[best_rows_idx].drop(columns='non_null_count')
df_best_positions = df_best_positions.reset_index(drop=True)


gw_infos = maj_gw_infos('CLASSIC')
daily_infos = maj_gw_infos('DAILY')
teams_df = get_teams()
players_df = get_players_by_team(teams_df)
players_infos_df = get_infos_players(players_df)
players_prices_df = get_lowest_prices_players(players_df)

df_merged = players_df \
    .merge(players_infos_df, on='slug', how='left')

df_to_export = df_merged.astype(object).where(pd.notna(df_merged), None)