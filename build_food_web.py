import pandas as pd
from pyvis.network import Network
from collections import Counter

# This CSV has come from the who-eats-whom iNaturalist project itself as an export
# https://www.inaturalist.org/projects/who-eats-whom
# If you go to Export Observations -> CSV, and then choose everything, you get this csv

df = pd.read_csv("observations.csv", low_memory=False)
print(df.shape)

# This prints out ['eater' 'thing being eaten' nan 'organism being eaten']
# This is actually supposed to be the OFV field value ids that are hardcoded on the frontend
# (12795, 12796). Tells us if this observations contains the species being eaten, or is eating
# I assume 'thing being eaten' and 'organism being eaten' is the same. The logic in the code uses this below
# For the NAN values, I am assuming it is something else, which you can see in the OFV.txt file
print(df['field:id meant for "eater" or organism being eaten?'].unique())

# Checking for Unique columns. Returns ['id', 'uuid', 'url'].
# ID is what we are using to get observations (what you see in the GET observation URLS and what is used
# in the frontend by Bradley)
# I am really not too sure what UIUD is used for, but Bradley has not been using it in the code. Maybe it 
# is a unique identifier for some other purpose we don't need?? iNaturalist Backend? I can't figure it out
# URL is the link to the observations. It uses "id" in the url instead of UIUD
unique_cols = [col for col in df.columns if df[col].is_unique]
print("Columns with all unique values")
print(unique_cols)

# Only take observations with proper quality grade. The Query to get this CSV is quality_grade=any&identifications=any&projects%5B%5D=who-eats-whom
# We only want research grades
df = df[df["quality_grade"] == "research"].reset_index(drop=True)

# Each observation has a partner URL if there is a partner in the observation, whether this observation
# is labeled as "eater" or "eaten"
# In the partner url,  we extract the "id" not "uiud"
def extract_partner_id(url_str):
    if not isinstance(url_str, str) or "/observations/" not in url_str:
        return None
    return url_str.rstrip("/").split("/")[-1]

# Make a new column with just the ID so we can create a map later 
df["partner_id"] = df['field:url for "partner" observation'].apply(extract_partner_id)
# Make it a string
df["id_str"] = df["id"].astype(str)

# We will change this in the future. Right now, I am not considering observations where there is no common
# name for the animal/species being referenced in the observation. Thus, the graph is not too big. 
df = df[df["common_name"].notna()].reset_index(drop=True)

# Map the id of the animal/species being referenced in an observation to its common name
id_to_name = dict(zip(df["id_str"], df["common_name"]))


edge_list = []
for _, row in df.iterrows():
    # IN JSON, with POSTMAN querys, this role field is actually just the hardcoded OFV values
    # (12795, 12796, etc). However, when I exported this CSV from iNaturalist itself, I guess it
    # organizes these values as text to make it easier? Also, it only exported the eater, eaten values 
    # and kept the rest as NaN on the CSV
    role = row['field:id meant for "eater" or organism being eaten?']
    # We will name the node as the common name
    this_name = row["common_name"]
    partner_id = row["partner_id"]
    if not isinstance(role, str) or not partner_id or not isinstance(this_name, str):
        continue
    if partner_id not in id_to_name:
        continue
    partner_name = id_to_name[partner_id]
    if not isinstance(partner_name, str):
        continue
    # IF the role is an eater, we will make this a predator-prey edge
    # The REASON why we were getting duplicate arrows, is because in the ELSE statement, I was also
    # saying if role_lc == anything but "eater" then prey, predator = this_name, partner_name. 
    # There is a second reason below
    role_lc = role.strip().lower()
    if role_lc == "eater":
        predator, prey = this_name, partner_name
    else:
        continue

    edge_list.append((predator, prey))
# Make edge list unique only. Sometimes there is multiple observations of a predator eating a prey
# This was another reason for duplicate edges
edge_list = list(set(edge_list))

print(f"Using {len(edge_list)} predator→prey edges for visualization.")

# We talked about adding some other things to the label when you hover over a node. These are the ones
# I am choosing for now. This is not final at all. I just wanted to see if I can do it.
# we can easily discuss about which columns to choose in the future
df[["taxon_kingdom_name", "taxon_class_name", "url", "description"]] = (
    df[["taxon_kingdom_name", "taxon_class_name", "url", "description"]]
    .fillna("Unidentified")
)

# This block was written by chatGPT
# Create a lookup dict where each unique common_name maps to its metadata (kingdom, class, url, description)
meta = (
    df
    .drop_duplicates("common_name")
    .set_index("common_name")[["taxon_kingdom_name", "taxon_class_name", "url", "description"]]
    .to_dict(orient="index")
)

# Build a predator set and prey set. THIS IS MEANT to help me color code the nodes
# We can discuss about what to do with this in the future
# More information below
predator_set = {p for p, _ in edge_list}
prey_set     = {q for _, q in edge_list}

net = Network(height="700px", width="100%", directed=True)
added_nodes = set()

# This is my optimized version of what we discussed in the meeting notes
# ALL COLOR CODE HASHES were given to me by CHAT GPT
for predator, prey in edge_list:
    for taxon in (predator, prey):
        # Add the node if it is not yet been added
        if taxon not in added_nodes:
            # If the animal in taxon is both a predator and prey in the dataset, make the node
            # orange. If it is just prey, make it greenish. If it is only a predator, make it red
            if taxon in predator_set and taxon in prey_set:
                color = "#F4A261"
            elif taxon in predator_set:
                color = "#E76F51"
            else:
                color = "#2A9D8F"
            # This is our metadata we are displaying when we hover over nodes. We should change in the
            # future. Right now, just seeing if I can do it. If data does not exist, placeholder is used
            info = meta.get(taxon, {
                "taxon_kingdom_name": "Unidentified",
                "taxon_class_name": "Unidentified",
                "url": "Unidentified",
                "description": "Unidentified"
            })
            # Create HTML for when you hover over the node
            title = (
                f"<b>{taxon}</b><br>"
                f"Taxon Kingdom Name: {info['taxon_kingdom_name']}<br>"
                f"Taxon Class Name: {info['taxon_class_name']}<br>"
                f"Example URL: <a href='{info['url']}' target='_blank'>{info['url']}</a><br>"
                f"Description: {info['description']}"
            )
            # Add nodes
            net.add_node(
                n_id=taxon,
                label=taxon,
                title=title,
                color=color
            )
            # Make sure we put this in our set so we don't have duplicate nodes
            added_nodes.add(taxon)

    net.add_edge(source=predator, to=prey, color="#333333")

net.write_html("predator_prey.html")


# THIS IS OUR CURRENT SEARCH INTERFACE
# We can improve search algorithm but it allows us to search specific nodes
# Actually works pretty well
html = open("predator_prey.html").read()
injected = """
<div style="position:absolute;top:10px;left:10px;z-index:999;">
  <input id="searchBox" placeholder="Search node" style="width:200px">
  <button onclick="caseInsensitiveFocus()">Go</button>
</div>
<script type="text/javascript">
  function caseInsensitiveFocus() {
    var val = document.getElementById('searchBox').value.trim().toLowerCase();
    var nodes = network.body.data.nodes.get();
    var match = nodes.find(function(n){
      return String(n.id).toLowerCase() === val;
    });
    if (match) {
      network.focus(match.id, {scale:1.5, animation:{duration:300}});
    } else {
      alert('Node not found: ' + val);
    }
  }
</script>
"""
html = html.replace("<body>", "<body>\n" + injected)
open("predator_prey.html", "w").write(html)