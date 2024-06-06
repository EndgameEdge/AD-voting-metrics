import requests
from datetime import datetime,timedelta
from dateutil import parser
import sys

def generate_dates(query_input):
    # Get today's date
    today = datetime.now().date()

    try:
        if 'to' in query_input:
            # Date range
            start_str, end_str = query_input.split(' to ')
            start_date = datetime.strptime(start_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_str, '%Y-%m-%d')

            # Check if end date is in the future
            if end_date.date() > today:
                print("The application cannot see into the future.")
                confirm = input("Would you like to limit the range to today's date? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    end_date = datetime.now()
                else:
                    print("Exiting.")
                    sys.exit()
        else:
            # Single date
            start_date = datetime.strptime(query_input, '%Y-%m-%d')

            # Check if the date is in the future
            if start_date.date() > today:
                print("The application cannot see into the future.")
                confirm = input("Would you like to query today's date instead? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    start_date = datetime.now()
                else:
                    print("Exiting.")
                    sys.exit()

            end_date = start_date

    except ValueError as e:
        print(f"Invalid date format: {e}. Please try again.")
        return None, None

    return start_date.date(), end_date.date()

# Define a function to retrieve data from each delegate.
def get_delegate_data():
  
    url = "https://vote.makerdao.com/api/delegates/v1?network=mainnet&sortBy=random"
    response = requests.get(url)
    data = response.json()

    delegate_list = data.get("delegates", [])

    return delegate_list

#Define a function to filter and retrieve the MKR for each delegate by date.
def get_mkr_delegated(address,data,end_date):
    # Perform a search in the delegate list
    delegate_info = next((info for info in data if info['voteDelegateAddress'].lower() == address.lower()), None)
  
    if delegate_info:
        earliest_date = datetime.strptime( delegate_info['blockTimestamp'] , '%Y-%m-%dT%H:%M:%S%z')

        mkr_locked_info = delegate_info.get("mkrLockedDelegate", [])
        mkr_locked_info.sort(key=lambda x: x["blockTimestamp"])
        
        if mkr_locked_info:
            mkr_delegated = 0
            for mkr_locked_delegate in mkr_locked_info:
                blockTimestamp_datetime = datetime.strptime(mkr_locked_delegate["blockTimestamp"], '%Y-%m-%dT%H:%M:%S%z').date()  
                if end_date >= blockTimestamp_datetime:
                    mkr_delegated = round(float(mkr_locked_delegate['callerLockTotal']), 4)
        else:
            mkr_delegated = 0

        return mkr_delegated, earliest_date.strftime("%Y-%m-%d")
    else:
        return None, None

#Define a function to retrieve the total MK held by each delegate by date.
def get_delegate_list_mkr(df,data,start_date,end_date):
    start_date_initial = start_date
    delegate_data_mkr = {'contract':{}, 'name':{}}
    for index,row in df.iterrows():
        start_date = start_date_initial
        delegate_name = row['Delegate Name'].strip().lower()
        delegate_contract = row['Delegate Contract']
        if delegate_name not in delegate_data_mkr['name']:
            delegate_data_mkr['name'][delegate_name] = {}
  
        if delegate_contract not in delegate_data_mkr['contract']:
            delegate_data_mkr['contract'][delegate_contract] = {}

        while start_date <= end_date:
            if start_date.strftime("%Y-%m-%d") not in delegate_data_mkr['name'][delegate_name]:
                delegate_data_mkr['name'][delegate_name][start_date.strftime("%Y-%m-%d")] = {'mkr':0}                
            if start_date.strftime("%Y-%m-%d") not in delegate_data_mkr['contract'][delegate_contract]:
                delegate_data_mkr['contract'][delegate_contract][start_date] = {'mkr':0}     

            mkr_delegated, earliest_date = get_mkr_delegated(delegate_contract,data,start_date)

            delegate_data_mkr['name'][delegate_name][start_date.strftime("%Y-%m-%d")]['mkr'] +=  mkr_delegated

            delegate_data_mkr['contract'][delegate_contract][start_date]['mkr'] =  mkr_delegated
            
            start_date += timedelta(days=1)   

    delegate_list_rank = []
    for delegate_name, data in delegate_data_mkr['name'].items():
        for date, data_mkr in data.items():        
            delegate_list_rank.append({
                'Delegate': delegate_name,
                'Total Delegation': data_mkr['mkr'],
                'Rank': 1,
                'Date': date
            })
    delegate_list_mkr = []
    for delegate_contract, data in delegate_data_mkr['contract'].items():
        for date, data_mkr in data.items():        
            delegate_list_mkr.append({
                'contract': delegate_contract.lower(),
                'mkr': data_mkr['mkr'],
                'date': date
            })

    return delegate_list_mkr,delegate_list_rank

# define a function to get the polls IDs for Data.
def get_poll_ids(start_date,end_date):
    poll_info = []   
    page = 0
    all_found = False
    while all_found is False:
        page = page + 1
        if not start_date:
            base_url = "https://vote.makerdao.com/api/polling/v2/all-polls?network=mainnet&pageSize=30&page={}&orderBy=FURTHEST_START"
            response = requests.get(base_url.format(page))
        else:
            base_url = "https://vote.makerdao.com/api/polling/v2/all-polls?network=mainnet&pageSize=30&page={}&orderBy=FURTHEST_START&startDate={}"
            response = requests.get(base_url.format(page,start_date.strftime("%Y-%m-%d")))
      
        data = response.json()
        # Make the API request
        paginationInfo = data.get("paginationInfo", [])
        polls = data.get("polls", [])
        
        if not paginationInfo: break
        if not polls: break

        for poll in polls:
            
            start_date_poll = parser.parse(poll['startDate']).date()

            if start_date_poll >= start_date and start_date_poll <= end_date:
                poll_info.append(poll)
                      
        if paginationInfo['numPages'] == 1 :  all_found = True

        if paginationInfo['numPages'] == page :  all_found = True

    return poll_info

# Define a function to confirm the voting of each delegate in the conducted polls.
def get_vote_poll_ids(poll_info,df,df_mkr):

    base_url = "https://vote.makerdao.com/api/polling/tally/{}?network=mainnet"
    
    for poll in poll_info:
        # Initialize an empty list to store vote status (Yes, Pending verification,No Delegated MKR or Not Started)
        vote_statuses = []
        # Make the API request
        response = requests.get(base_url.format(poll['pollId']))
        data = response.json()
        for index,row in df.iterrows():
            address = row['Delegate Contract']
            first_delegate_date = datetime.strptime( row['Start Date'] , '%Y-%m-%d').date()
            # Check if the address voted in this poll
            voted = any(voter['voter'].lower() == address.lower() for voter in data.get("votesByAddress", []))
            
            start_date =  parser.parse(poll['startDate']).date()
            end_date = parser.parse(poll['endDate']).date()
            
            delegates_mkr_available = df_mkr[(df_mkr['contract'].str.lower() == address.lower()) & 
                                  (df_mkr['date'] >= start_date) & 
                                  (df_mkr['date'] <= end_date)]
            
            for index,delegate_mkr_available in delegates_mkr_available.iterrows():

                if delegate_mkr_available['mkr'] != 0 :
                    if voted:
                        voted = 'Yes'
                    else:
                        voted = 'No'
                    break
                else:
                    voted = 'No Delegated MKR'

 
            if first_delegate_date > end_date:
                voted = 'Not Started'                

            vote_statuses.append(voted)
        
        # Add a new column to the DataFrame with the poll id as the header
        df[str(poll['pollId'])] = vote_statuses

    return df

# define a function to get the executes IDs for Data.
def get_execute_ids(start_date,end_date):
    
    spell_info = []
    start = 0
    limit = 100 
    while start < 10000000:
     
        base_url = "https://vote.makerdao.com/api/executive?start={}&limit={}"
        response = requests.get(base_url.format(start,limit))
     
        data = response.json()

        if not data: break     

        for execute in data:
            date_execute = parser.parse(execute['date'].replace('(Coordinated Universal Time)', '')).date()

            if date_execute >= start_date and date_execute <= end_date:
                spell_info.append({'address':execute['address'].lower(),'startDate':date_execute,'title':execute['title']})        
          
        start = start + limit

    return spell_info

# Define a function to confirm the voting of each delegate in the spells.
def get_vote_execute_ids(spell_info,df,df_mkr):
    url = "https://vote.makerdao.com/api/executive/supporters?network=mainnet"
    # Make the API request
    response = requests.get(url)
    data = response.json()
   
    for spell in spell_info:
        # Initialize an empty list to store vote status (Yes, Pending verification,No Delegated MKR or Not Started)
        vote_statuses = []
        spell_address = spell['address']
        start_date = spell['startDate']

        for index,row in df.iterrows():
            address = row['Delegate Contract']
            first_delegate_date = datetime.strptime( row['Start Date'] , '%Y-%m-%d').date()

            if spell_address in data:            
                # Check if the address voted in this spell                
                voted = any( supporters['address'] == address.lower() for supporters in data[spell_address])                
            else:
                voted = False

            delegates_mkr_available = df_mkr[df_mkr['contract'].str.lower() == address.lower() ]
            
            for index,delegate_mkr_available in delegates_mkr_available.iterrows():
       
                if delegate_mkr_available['date'] != start_date : continue

                if delegate_mkr_available['mkr'] != 0 :
                    if voted:
                        voted = 'Yes'
                    else:
                        voted = 'Pending verification'
                    break
                else:
                    voted = 'No Delegated MKR'

            if first_delegate_date > start_date:
                voted = 'Not Started'

            vote_statuses.append(voted)
        
        # Add a new column to the DataFrame with the poll id as the header
        df[str(spell_address)] = vote_statuses

    return df

# Define the custom sorting function
def custom_sort(df,hardcoded_order,poll_info,spell_info):
    # Define your hardcoded order array
    df = df.drop(['MKR Delegated','Start Date', 'End Date','End Reason'], axis=1)

    df.insert(df.columns.get_loc('Delegate Contract') + 1, 'Delegate', df['Delegate Name'].str.cat(df['Aligned Voter Committee'], sep='-'))

    df.drop(['Delegate Name', 'Aligned Voter Committee'], axis=1, inplace=True)

    # Get the names of all columns in the DataFrame
    column_names = df.columns

    # Lists to store the values
    title_list = []
    startDate_list = []
    endDate_list = []

    # Search for objects and store values in lists
    for column_name in column_names:
            
        object_found = next((obj for obj in poll_info if str(obj['pollId']) == str(column_name)), None)        
        if not object_found:
            object_found = next((obj for obj in spell_info if str(obj['address']) == str(column_name)), None)        
       
        if object_found:
            title_list.append(object_found['title'])

            if isinstance(object_found['startDate'], str):
                startDate_list.append(parser.parse(object_found['startDate']).date())
            else:
                startDate_list.append(object_found['startDate'])

            try:                
                if isinstance(object_found['endDate'], str):                   
                    endDate_list.append(parser.parse(object_found['endDate']).date())
                else:
                    endDate_list.append(object_found['endDate'])
            except Exception as e:
                endDate_list.append('N/A')          
            
        else:
            title_list.append('Title')
            startDate_list.append('Start Date')
            endDate_list.append('End Date')  
             
    # Identify the missing rows in hardcoded_order.
    missing_rows = [row for row in hardcoded_order if row.lower() not in df['Delegate Contract'].str.lower().tolist()]

    num_columns = len(df.columns)
    # Add blank rows at the beginning of the DataFrame for the missing elements.
    for row in missing_rows:
        blank_row = [None] * num_columns 
        blank_row[0] = row
        df.loc[len(df)] = blank_row  # Add a row with the contract and a null value for Age.

    # Create a new column for sorting based on the custom_sort function
    df['SortKey'] = df['Delegate Contract'].apply(lambda x: hardcoded_order.index(x.lower()) if x.lower() in hardcoded_order else len(hardcoded_order))

    # Sort the DataFrame using the SortKey column
    sorted_df = df.sort_values(by='SortKey')

    # Remove the SortKey column if no longer needed
    sorted_df.drop(columns=['SortKey'], inplace=True)

    sorted_df.rename(columns={'Delegate Contract': '', 'Delegate': 'Poll Id'}, inplace=True)

    transposed_df = sorted_df.transpose()    
    
    transposed_df.insert(0, 'Start Date',startDate_list)   
    transposed_df.insert(1, 'End Date', endDate_list)
    transposed_df.insert(2, 'Title', title_list) 

    return transposed_df
