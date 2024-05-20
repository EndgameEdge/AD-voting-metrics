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
def custom_sort(df,poll_info,spell_info):
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
  
    hardcoded_order = [
        '0xedc6c08960f517f233e8b6f5a5a61b6b19834def','0xfe61acc408b63a5a03507a224398fa1fe8143f28',
        '0xb18680092734394295d0591bb42f2bd3c184517e','0x907fea3a32215993cd6734402044f0957e1a3078',
        '0x4d8c9c2cd8846533967b07becfc437542196ad6a','0xc2daea14891fc47ee76368ce7c54c7b200fba672',
        '0x918d368ea7bbe3af0f4ec9172802f8badae01284','0x952dc79bcee652aad8cc9268d9c614fa166d0c1d',
        '0x62060879dfbb6def3b73cfc48f1f0595c0fed505','0xca0c8bedc85c2ec9b0dfb42b3f2763486ddea1b6',
        '0xb086ec4303dc1514c09618c6c68ee444d6eee041','0xa67f820945da8634d5b54fe09ca74b1559b7ff39',
        '0xe2bfda5e1f59325e4b8df5feaa30e4ab6516bf28','0xa346c2eea05bb32c986ff755b2f19d2f0ba8d14c',
        '0x475efac48a0a18660a7a26ee6bd5febf466930f8','0xC0E23144db36101453BA5c426445ca5Bf20f6b71',
        '0x7938b304F1c28e85b6A021251C8CeefF20370f38','0xc3b85930deca88e5bcb48fa8ebe935f97d5e412b',
        '0x1dd6c65e6e22f196d5c2209f439d1f07d02ba7a4','0x1D71861f54Aa6E63add5AcfC70E0E4bA9Fd9f259',
        '0xb6ca415fc42b3f96641d14280c3f3a0f078e50e5','0xddecead383f2c22b4755ab32f56d48a4a1415258',
        '0x8cc777ed9eb3a3b9087591697ecb7f60f256ce4f','0x58dc40b5f9f0758ee43b0a208fe362c90fdfad4d',
        '0xa4b28dd898a885cce88caa00261d9fe6ceed32bb','0x8ea48c2264f1e5998c3ab3df3037903f8fae0caa',
        '0xAB3fD902E4dad36c6b31E3954A8dE14Dd829533c','0xfbec297af3f4925966ab295a0771c420a9e85e08',
        '0xa2c669dc868be0a2a8d6c0ad715e17f45035ba76','0x69b576a7e193a15a570ee5bb2149deb3f03537a2',
        '0x5b4870014313c808c374f8ed1ab5b78813eb9c7f','0x45C52826EFA13A6DE713528BF42B520C9fA50081',
        '0x0a907fe3adb890db7db27a7f21e188a4127b2e7c','0xdbb451BFd4e6E461caa2C8bf0dC83346A211c29C',
        '0x644c092a5ccafc425ebf133123299a6397ae97d9','0x87686c4dd2ffd8e0b01f716eea1573f829737e97',
        '0x27194176525a0088e3dc96973b22b01b15376ebd','0x51f3067cb6a1185d1e8316332921d9501fc4c006',
        '0x3200c191cc245b3e2de3fd3b3087104f3f313f57','0x5b0a4932dc9e253f9b15fd69f07b68e9874ea794',
        '0x445cb6c63c502fdbebd1b273f6aea1aad691e0aa','0xb335e8b70f95f28e79acf58491751f83b0050888',
        '0x36124cee63ae786eea41bda0fb61b1b946e4c08c','0x117B58Cc89156b48c302aAa4832A19C1c1Aa124C',
        '0x5d97f2af00c767b7333fdc2b58d10faff9f51024','0x47EcD8e9f8F299cE47E3aB891a874707d70A3aF9',
        '0x911682CB21d7e5bdc75544fB1FCf0Fb8E9635AcF','0x204A2B6ab6A675D1f82634F92799Ced2bDD641A2'
    ]

  
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
