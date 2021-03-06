import os
import sys
import ccxt
import numpy as np
import pandas as pd
import random
# ------------------------------------------------------------------------------
list1 = ['a', 'b', 'c', 'd']
list2 = [1, 2, 3, 4]
list3 = [['A','B'],['C','D'],[5,6],[7,8]]

for num, (a, b, c) in enumerate(zip(list1,list2,list3)):
	print(num, a, b, c)



# ------------------------------------------------------------------------------

def simulate_HODL():
	simulations = pd.DataFrame(index=sim_dates)

	for sim_num in range(1000):
		# Randomly select basket of coins
		random_list = random.sample(range(len(coins)-1), num_coins)

		# Determine amount of each coin bought on day 0
		coin_amts = amt_each / historical_prices[0, random_list]

		# Use coins as column name
		col = '-'.join([coins[i] for i in random_list])

		# Dot multiply list of coin amounts with array of historical prices of selected coins
		simulations[col] = historical_prices[:, random_list].dot(coin_amts)

	simulations.to_csv(file_path +  'HODL.csv')
	return simulations


def simulate_rebalance(df):

	# Set the threshold of weight difference to trigger a trade
	thresh = 0.05
	avg_weight = 1 / num_coins
	weighted_thresh = np.float32(avg_weight * thresh)

	# Exclude date column
	cols = df.columns.tolist()
	hodl_simulations = np.array(df)

	# Create arrays to be transformed to CSV's
	simulation_summary = [[] for x in range(len(cols))]
	rebalance_simulations = np.empty(shape=(len(cols), len(historical_prices)))
	num_simulation = 0

	# Use the same coin combinations as the HODL simulation
	coin_lists = [col.split('-') for col in cols]

	# For each simulation, convert the symbol into the corresponding column # in historical_prices
	coin_lists_indexes = [[coins.index(coin) for coin in coin_list] for coin_list in coin_lists]

	for col, coin_list, coin_list_index in zip(cols, coin_lists, coin_lists_indexes):

		fees, trade_count, trades_eliminated, taxes_rebalanced = 0, 0, 0, 0
		daily_totals = [start_amt]

		# Reduce historical_prices array to only the coins used in the simulation
		small_historical_prices = historical_prices[:, coin_list_index]

		# Initial purchase prices for coins
		purchase_prices = small_historical_prices[0].tolist()

		# Calculate starting coin amounts
		coin_amts = amt_each / small_historical_prices[0]


		# Simulate each day
		for num_day in range(1,len(historical_prices)):
			while True:
				dollar_values = small_historical_prices[num_day] * coin_amts
				total_dollar_value = sum(dollar_values)
				l_index, h_index = dollar_values.argmin(), dollar_values.argmax()

				# See how far the lightest and heaviest coin weight deviates from average weight
				weight_to_move = min([avg_weight - dollar_values[l_index]/total_dollar_value, dollar_values[h_index]/total_dollar_value - avg_weight])

				if weighted_thresh > weight_to_move:
					break

				# Does a ticker for the coins exist? - if it doesn't, it needs to convert to BTC first, which takes two trades
				ratios = {coin_list[l_index] + '/' + coin_list[h_index], coin_list[h_index] + '/' + coin_list[l_index]}
				ticker = ratios & tickers

				if not ticker:
					trade_count += 2
					rate = 0.005
				else:
					trade_count += 1
					rate = 0.0025
					trades_eliminated += 1

				dollar_amt = weight_to_move * total_dollar_value
				fees += (dollar_amt * rate)

				# Get coin quantities to buy/sell based on current market price
				l_quantity = dollar_amt / small_historical_prices[num_day, l_index]
				h_quantity = dollar_amt / small_historical_prices[num_day, h_index] * (1 + rate)

				price_difference = small_historical_prices[num_day, h_index] - purchase_prices[h_index]

				taxes_rebalanced += (price_difference * h_quantity * 0.25)

				# adjust avg purchase price for bought coin
				purchase_prices[l_index] = (purchase_prices[l_index] * coin_amts[l_index] + small_historical_prices[num_day, l_index] * l_quantity)/(coin_amts[l_index] + l_quantity)

				# Adjust coin quantities
				coin_amts[l_index] += l_quantity
				coin_amts[h_index] -= h_quantity

			# document total portfolio value on that day
			daily_totals.append(np.dot(small_historical_prices[num_day], coin_amts))

		# Document important features of the simulations
		end_price_HODL = hodl_simulations[len(hodl_simulations)-1, num_simulation]
		taxes_HODL = (end_price_HODL - 5000) * .25

		end_price_rebalanced = daily_totals[len(daily_totals)-1]
		simulation_summary[num_simulation] = [col, fees, trade_count, trades_eliminated, taxes_HODL, end_price_HODL, taxes_rebalanced, end_price_rebalanced]

		rebalance_simulations[num_simulation] = daily_totals
		num_simulation += 1

	rebalance_simulations = pd.DataFrame(np.transpose(rebalance_simulations), columns=cols, index=sim_dates)
	rebalance_simulations.to_csv(file_path +  'rebalanced.csv')

    simulation_summary = pd.DataFrame(
        simulation_summary,
        columns=
        [
            'portfolio',
            'total_fees',
            'num_trades',
            'num_trades_saved',
            'taxes_HODL',
            'end_price_HODL',
            'taxes_rebalanced',
            'end_price_rebalanced'
        ]
    )

	simulation_summary.to_csv(file_path + 'summary.csv', index=False)


if __name__ == '__main__':

	file_path = 'C:/Users/18047/Documents/Github/Thinkful Projects/Final Capstone/data/'
	historical_prices = pd.read_csv(file_path + 'historical_prices.csv')

	coins = historical_prices.columns.tolist()[1:]

	# Exclude date column from historical prices
	historical_prices = np.array(historical_prices[coins])

	# get date ranges used for simulations
	historical_cap = pd.read_csv(file_path + 'historical market cap.csv')
	historical_cap = np.array(historical_cap)

	start_dates = historical_cap[:len(historical_cap) - 365]
	end_dates = historical_cap[365:]

	# Subtract the ending market caps from each other, located in the 4th column
	cap_diffs = list(end_dates[:, 3] - start_dates[:, 3])

	# Make sure there's an odd number of dates, so the median value can be indexed
	if len(cap_diffs) % 2 == 0:
		cap_diffs.pop(len(cap_diffs)-1)

	# Start date for simulations
	start_date = cap_diffs.index(np.median(cap_diffs))

	# Limit dataframe dates to the date range
	historical_prices = historical_prices[start_date:start_date + 365]
	sim_dates = sim_dates[start_date:start_date + 365]

	# Retrieve all current tickers on exchange
	exchange = ccxt.bittrex()
	tickers = set()
	[tickers.add(ticker) for ticker in exchange.fetch_tickers()]

	# Start with $5000 of Bitcoin at day 0 price
	start_amt = 5000
	num_coins = 5
	amt_each = start_amt / num_coins

	df = simulate_HODL()
	simulate_rebalance(df)
