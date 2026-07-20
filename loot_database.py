import os
import pandas as pd
import dropbox
from dotenv import load_dotenv

load_dotenv()


dbx = dropbox.Dropbox(
    app_key=os.getenv("DROPBOX_APP_KEY"),
    app_secret=os.getenv("DROPBOX_APP_SECRET"),
    oauth2_refresh_token=os.getenv("DROPBOX_REFRESH_TOKEN")
)



def download_excel():

    dropbox_path = "/Sand-Loot-Locations.xlsx"
    local_file = "Sand-Loot-Locations.xlsx"


    print("Downloading Excel file...")


    metadata, response = dbx.files_download(
        dropbox_path
    )


    with open(local_file, "wb") as f:
        f.write(response.content)


    print("Excel downloaded!")


    return local_file





def clean(value):

    if pd.isna(value):
        return None

    return str(value).strip()





def load_loot_database():


    file = download_excel()



    loot_sheet = pd.read_excel(
        file,
        sheet_name="Loot Locations"
    )


    excel = pd.ExcelFile(file)

    print("AVAILABLE SHEETS:")
    print(excel.sheet_names)

    crafting_sheet = pd.read_excel(
        file,
        sheet_name="Crafting"
    )
    print(crafting_sheet.columns.tolist())
    print(crafting_sheet.head())

    price_sheet = pd.read_excel(
        file,
        sheet_name="Price Sheet"
    )



    database = {}



    # ==================================
    # LOAD PRICE INFORMATION
    # ==================================

    for _, row in price_sheet.iterrows():


        item = clean(row["Item"])


        if not item:
            continue



        item = item.upper()



        if item not in database:
            database[item] = {}

        database[item].update({

            "price": row["Price"],
            "rarity": clean(row["Rarity"]),
            "category": clean(row["Category"])

        })

        database[item].setdefault("locations", [])
        database[item].setdefault("crafting", [])




    # ==================================
    # LOAD NORMAL LOOT LOCATIONS
    # ==================================

    for _, row in loot_sheet.iterrows():


        item = clean(row["Item"])


        town = clean(row["Town"])


        details = clean(row["More Details"])



        if not item:
            continue



        item = item.upper()



        if item not in database:

            database[item] = {

                "price": None,

                "rarity": None,

                "category": None,

                "locations": [],

                "crafting": []

            }




        amount = row["Amount seen"]

        if pd.notna(amount):
            amount = int(amount)
        else:
            amount = None


        location_entry = {

            "town": town,

            "amount": amount,

            "details": []

        }




        if details:

            location_entry["details"].append(
                details
            )



        database[item]["locations"].append(
            location_entry
        )





    # ==================================
    # LOAD CRAFTING RECIPES
    # ==================================

    for _, row in crafting_sheet.iterrows():

        output = clean(row["Crafting Output"])

        if not output:
            continue


        if output not in database:

            database[output] = {

                "price": None,
                "rarity": None,
                "locations": [],
                "crafting": []

            }



        inputs = []


        input1 = clean(
            row["Crafting Input 1"]
        )

        input2 = clean(
            row["Crafting Input 2"]
        )


        amount = clean(
            row["Input Amount"]
        )


        if input1:

            inputs.append({

                "item": input1,
                "amount": amount

            })


        if input2:

            inputs.append({

                "item": input2,
                "amount": amount

            })



        database[output]["crafting"].append({

            "town": clean(row["Town"]),

            "inputs": inputs,

            "output_amount": clean(
                row["Output Amount"]
            )

        })




    return database