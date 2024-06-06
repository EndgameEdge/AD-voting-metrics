import os
import pandas as pd
import maker_dao as maker

# Get the current directory

script_dir = os.path.dirname(os.path.abspath(__file__))

while True:
    # Step 1: Read the CSV file
    file_path = os.path.join(script_dir, 'delegate_data', 'Aligned Delegates.csv')
    df = pd.read_csv(file_path)
    #Get a list of the order to use in the spreadsheet
    df_spreadsheet = pd.read_csv(os.path.join(script_dir, 'delegate_data', 'order spreadsheet.csv'))

    hardcoded_order = df_spreadsheet['contract'].str.lower().tolist()

    # Create DataFrames to store results
    df_ranking = pd.DataFrame()

    # Prompt user input for query date
    query_input = input("\nEnter the date to query (YYYY-MM-DD), or a range (YYYY-MM-DD to YYYY-MM-DD):")
    
    # Generate dates from user input
    start_date, end_date = maker.generate_dates(query_input)

    # Check if valid dates were entered
    if start_date is None and end_date is None: 
        continue

    print('Getting information...')
    # Get delegate data from API
    delegate_list = maker.get_delegate_data()

    # Check if API data was retrieved successfully
    if not delegate_list:
        print("Problems getting data from the API. Please try again.")
        continue

    # Get MKR delegated for each delegate contract
    print('Getting MKR...')
    df['MKR Delegated'], df['Start Date'] = zip(*df['Delegate Contract'].apply(lambda x: maker.get_mkr_delegated(x, delegate_list, end_date)))

    # Get delegate list and MKR ranking
    print('Getting RANKING...')
    delegate_list_mkr, delegate_list_rank = maker.get_delegate_list_mkr(df, delegate_list, start_date, end_date)

    # Create DataFrames to store results
    df_mkr = pd.DataFrame(delegate_list_mkr)
    df_ranking = pd.DataFrame(delegate_list_rank)

    # Sort DataFrames by date and delegated MKR
    df_mkr = df_mkr.sort_values(by=['date', 'mkr', 'contract'], ascending=False)
    df_ranking = df_ranking.sort_values(by=['Date', 'Total Delegation'], ascending=False)
    
    # Calculate and assign ranks to delegates
    current_rank = 1
    prev_date = None
    prev_total_delegation = None
    ranks = []

    for index, row in df_ranking.iterrows():
        if row['Date'] != prev_date:
            current_rank = 1
        ranks.append(current_rank)
        current_rank += 1
        prev_date = row['Date']        

    df_ranking['Rank'] = ranks
    df_ranking = df_ranking.sort_values(by=['Rank','Date'], ascending=[True, True])

    df = df.sort_values(by='MKR Delegated', ascending=False)

    # Get poll IDs information and vote from polls
    print('Getting POLL IDS...')
    POLL_INFO = maker.get_poll_ids(start_date, end_date)
    print('Getting VOTE FROM POLLS...')
    df = maker.get_vote_poll_ids(POLL_INFO, df, df_mkr)

    # Get SPELL addresses information and vote from SPELL
    print('Getting SPELL addresses...')
    SPELL_INFO = maker.get_execute_ids(start_date, end_date)
    print('Getting VOTE FROM SPELL...')
    df = maker.get_vote_execute_ids(SPELL_INFO, df, df_mkr)
    
    # Save data to CSV files
    output_csv = os.path.join(script_dir, 'output_data', 'vote_participation.csv')
    df.to_csv(output_csv, index=False)
    print(f"Participation vote data saved to {output_csv}")

    df = maker.custom_sort(df,hardcoded_order,POLL_INFO,SPELL_INFO)
  
    output_csv = os.path.join(script_dir, 'output_data', 'mkr.csv')
    df_mkr.to_csv(output_csv, index=False)
    print(f"MKR data by date saved to {output_csv}")

    output_csv = os.path.join(script_dir, 'output_data', 'ranking.csv')
    df_ranking.to_csv(output_csv, index=False)
    print(f"Ranking data saved to {output_csv}")
        
    output_csv = os.path.join(script_dir, 'output_data', 'vote_participation_final_transposed.csv')
    df.to_csv(output_csv, header=False, index=True)
    print(f"(transposed) Participation vote data saved to {output_csv}")
 
    # Ask if another query is desired
    continue_query = input("\nDo you want to query another date? (yes/no): ").strip().lower()
    if continue_query != 'yes':
        break
