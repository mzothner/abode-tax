import streamlit as st
import os
from datetime import datetime
from typing import List
import requests
from dotenv import load_dotenv
import webbrowser
from streamlit_searchbox import st_searchbox
from google.oauth2 import service_account
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import toml
import folium


def main():
    st.set_page_config(page_title="Abode Insights")

    # ----- SIDEBAR -----
    def open_webpage(url):
        webbrowser.open_new_tab(url)

    
    st.sidebar.image("images/abode logo.png", width=150)
    st.sidebar.write("Abode simplifies homeownership for millions of Americans with personalized home insights and a smart assistant that helps you on your home journey.") 
    st.sidebar.markdown(" ")
    if st.sidebar.button("Join the Waitlist"):
        webpage_url = "https://joinabode.ai?utm_source=tax_tool_sidebar"  # Replace this with your desired URL
        open_webpage(webpage_url)
    st.sidebar.markdown(" ")    
    st.sidebar.image("images/abode mvp.png", width=200)

    # ----- MAIN PAGE HEADER -----

    st.title("Property Tax Challenger 💰")
    waitlist_url_1 = "https://joinabode.ai?utm_source=tax_tool_header"
    st.write(f"A tool from [Abode]({waitlist_url_1})")
    st.subheader("Are you a good candidate to challenge your property taxes?")
    st.caption("Your county may overcharge you on taxes due to your home's assessed value. If you believe your property is actually worth less, you can dispute your taxes to pay a fair amount. This varies by county and state.")

    
    # ------ MAIN PAGE TABS ------

    google_maps_api = st.secrets["GOOGLE_MAPS_API"]
    attom_api_key = st.secrets["ATTOM_API"]


    def get_place_autocomplete(address):
        endpoint = f"https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = {
            "input": address,
            "key": google_maps_api,
        }
        response = requests.get(endpoint, params=params,timeout=5)
        if response.ok:
            data = response.json()
            results = [prediction['description'] for prediction in data['predictions']]
            return results
        else:
            return None

    # function with list of labels
    def search_maps(address: str) -> List[any]:
        return get_place_autocomplete(address) if address else []

    # pass search function to searchbox
    address = st_searchbox(
        search_maps,
        key="address_searchbox",
        default=None,
        placeholder="Enter your property address",
        label="See how much you can save",
        clear_on_submit=False
    )

    # Initialize the count if it doesn't exist yet
    if 'count' not in st.session_state:
        st.session_state.count = 0

    button_clicked = st.button("Submit", key="address_submit")

    # If an address is selected and button is clicked
    if button_clicked:

        if st.session_state.count >= 3:
            st.warning("You've reached the limit of 3 submissions in this session. Please try again later.")

        else:
            # Increase the count by one
            st.session_state.count += 1

            # If an address is selected
            if address:
                headers = {
                    "Accept": "application/json",
                    "apikey": attom_api_key
                }

                url = "https://api.gateway.attomdata.com/propertyapi/v1.0.0/attomavm/detail?"
                params = {
                    "address1": address.split(",")[0],  # Get street from address
                    "address2": ", ".join(address.split(",")[1:])  # Get city and state from address
                }

                response = requests.get(url, headers=headers, params=params,timeout=5)

                # Check the status code to ensure the request was successful
                if response.status_code == 200:
                    data = response.json()

                    # Extract specific information from the API response
                    address = data['property'][0]['address']['oneLine']
                    avm_value = int(data['property'][0]['avm']['amount']['value'])
                    assdttlvalue = int(data['property'][0]['assessment']['assessed']['assdttlvalue'])
                    last_avm_calculation = data['property'][0]['avm']['eventDate']
                    
                    difference = abs(avm_value - assdttlvalue)
                    difference_currency = "${:,.2f}".format(difference)
                    avm_value_currency = "${:,.2f}".format(avm_value)
                    assdttlvalue_currency = "${:,.2f}".format(assdttlvalue)

                    percentage_low = difference * .008
                    percentage_high = difference * .022

                    percentage_low_currency = "${:,.2f}".format(percentage_low)
                    percentage_high_currency = "${:,.2f}".format(percentage_high)

                    # Get the current date and time
                    submission_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # GOOGLE SHEET API

                    # use creds to create a client to interact with the Google Drive API
                    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
                    
                    # Reconstruct the service account info from the secrets
                    gcp_service_account = {
                        "type": st.secrets["type"],
                        "project_id": st.secrets["project_id"],
                        "private_key_id": st.secrets["private_key_id"],
                        "private_key": st.secrets["private_key"],
                        "client_email": st.secrets["client_email"],
                        "client_id": st.secrets["client_id"],
                        "auth_uri": st.secrets["auth_uri"],
                        "token_uri": st.secrets["token_uri"],
                        "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
                        "client_x509_cert_url": st.secrets["client_x509_cert_url"]
                    }

                    creds = service_account.Credentials.from_service_account_info(gcp_service_account,scopes=scope)
                   
                    # Authorize the client
                    client = gspread.authorize(creds)
                    
                    # Accessing a worksheet by its title
                    sheet_url = st.secrets["private_gsheets_url"]
                    worksheet = client.open(sheet_url).worksheet("Eng_Mkt_Tools")

                    # Adding submissions to marketing analytics document to measure later
                    data_to_append = [address, avm_value, assdttlvalue, submission_datetime]
                    worksheet.append_row(data_to_append)
                    
                    # Call Google Maps API if response goes through
                    
                    def get_coordinates_from_address(address):
                        url = f'https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={google_maps_api}'
                        response = requests.get(url)
                        data = response.json()
                        if data['status'] == 'OK':
                            location = data['results'][0]['geometry']['location']
                            return location['lat'], location['lng']
                        else:
                            print(f"Geocoding API call failed with {response}")
                            return None
                        
                    def create_map_with_marker(latitude, longitude):
                        map_obj = folium.Map(location=[latitude, longitude], zoom_start=15)
                        folium.Marker([latitude, longitude], popup=address).add_to(map_obj)
                        return map_obj
                    
                    
                    # Print data to Streamlit
                    st.divider()
                    if avm_value < assdttlvalue:
                        st.balloons()
                        st.success("You're a good candidate to challenge your property taxes!")
                        st.write("Your property taxes are based on the assessed value of your home, so you want this number to be as low as possible. Based on your current market value, we think you have a good chance of lowering your assessed value.")
                    else:
                        st.info("You're not a good candidate to challenge your property taxes at this time. Your assessed value would need to be higher than your market value in order to challenge property taxes.")
                        st.write("Don't fret. We can deliver more personalized home insights like this one. Sign up for the waitlist to get access to Abode when we launch.")

                    st.markdown(" ")
                    with st.container():
                        col1, col2 = st.columns(2)

                        with col1:
                            st.subheader("Your market value")
                            st.subheader(f"{avm_value_currency}")
                            st.subheader("Your assessed value")
                            st.subheader(f"{assdttlvalue_currency}")
                            st.write("We'd love to stay in touch to help you challenge your property taxes next tax season. Join the waitlist as we gear up for launch.")
                            st.markdown(" ")
                            st.markdown(" ")

                            if avm_value < assdttlvalue:
                                st.subheader("Potential tax savings")
                                st.write("Based on your current market value, we think you have a good chance of lowering your assessed value. Lower assessed value, lower property taxes.")
                                st.info(f"Low end estimate: {percentage_low_currency}")
                                st.info(f"High end estimate: {percentage_high_currency}")

                        with col2:
                            st.write(f"That's a difference of {difference_currency}")
                            st.write(f"Market value last calculated {last_avm_calculation}")
                            st.write("This estimate is based on recent public data from your county. Specific values regarding your property will change this result.")

                            # Get the latitude and longitude from the address
                            coords = get_coordinates_from_address(address)

                            if coords:
                                # Create the map and add a marker at the location
                                map_with_marker = create_map_with_marker(*coords)
                                print(map_with_marker)
                                
                                # Convert the map object to HTML
                                map_html = folium.Figure().add_child(map_with_marker)
                                
                                # Display the map in Streamlit using HTML
                                st.components.v1.html(map_html._repr_html_(), height=300)
                    st.divider()
                    with st.container():
                        col1, col2 = st.columns(2)

                        with col1:
                            st.image("images/taxes.png")
                            st.subheader("Need help challenging your taxes?")
                            st.write("Millions of homeowners overpay their property taxes every year. In some states, you can challenge the assessment of your home, reducing your tax burden for the year.")
                            st.caption("Some people can save thousands! 💸")
                        
                        with col2:
                            st.image("images/kitchen.png")
                            st.subheader("How does Abode help with this?")
                            st.write("Abode helps you put financial decisions on autopilot. We'll recommend savvy financial moves and ensure you're not missing out on savings opportunities.")
                            st.caption("We'll help you level up your homeownership 💪")


                    st.divider()
                    st.subheader("Want more personalized insights for your home?")
                    st.write("Effortless, automated homeownership is a tap away.")
                        
                    waitlist_url = "https://joinabode.ai?utm_source=tax_tool_footer"

                    # Using Markdown syntax to create a hyperlink
                    st.subheader(f"[Join the waitlist for Abode]({waitlist_url})")
                


            

                else:
                    # Handle the API request failure
                    st.warning("Not all address formats will work. Try formatting your address like '123 Main St, San Francsico, CA'")
                    st.warning("Try 'Avenue' for 'Ave', '#1' for 'Unit 1', etc.")
                    print("API request failed with status code:", response.status_code)


            # ----- MAIN PAGE FOOTER -----


if __name__ == "__main__":
    main()

