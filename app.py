import folium
from folium.plugins import MarkerCluster
import os
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# Page layout
st.set_page_config(page_title="AZDOT Drainage Asset Search", layout="wide")


# Load data (Cached)
@st.cache_data
def load_data():
  output_file = "drainage_assets.parquet"
  # Fallback to CSV if parquet isn't present
  if os.path.exists(output_file):
    df = pd.read_parquet(output_file)
  else:
    df = pd.read_csv("drainage_assets.csv")
  df.columns = df.columns.str.strip()
  return df


df = load_data()

# Ensure numeric types for coordinates and mileposts
mp_from_col = "From MP/Offset"
if mp_from_col in df.columns:
  df[mp_from_col] = pd.to_numeric(df[mp_from_col], errors="coerce")
if "Lat" in df.columns and "Long" in df.columns:
  df["Lat"] = pd.to_numeric(df["Lat"], errors="coerce")
  df["Long"] = pd.to_numeric(df["Long"], errors="coerce")

# --- NAVIGATION SIDEBAR ---
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select Tool Mode",
    [
        "Filter & Search Tool",
        "Batch Asset ID Lookup & Sort",
        "Map Area Search",
    ],
)

# ==========================================
# PAGE 1: ORIGINAL FILTER & SEARCH TOOL
# ==========================================
if page == "Filter & Search Tool":
  st.title("Arizona Highways Stormwater Drainage Assets Search")
  st.markdown(
      "Filter through 180,000+ drainage assets and access direct links to ADOT"
      " records and maps."
  )

  st.sidebar.header("Filter Assets")

  features = ["All"] + sorted(df["Feature"].dropna().unique().tolist())
  selected_feature = st.sidebar.selectbox("Feature", features)

  routes = ["All"] + sorted(df["Route"].dropna().unique().astype(str).tolist())
  selected_route = st.sidebar.selectbox("Route", routes)

  directions = [
      "All"
  ] + sorted(df["Direction"].dropna().unique().astype(str).tolist())
  selected_direction = st.sidebar.selectbox("Direction", directions)

  ramp_nums = [
      "All"
  ] + sorted(df["Ramp #"].dropna().unique().astype(str).tolist())
  selected_ramp_num = st.sidebar.selectbox("Ramp #", ramp_nums)

  ramp_ids = [
      "All"
  ] + sorted(df["Ramp ID"].dropna().unique().astype(str).tolist())
  selected_ramp_id = st.sidebar.selectbox("Ramp ID", ramp_ids)

  st.sidebar.markdown("### Milepost Range")
  min_mp = st.sidebar.number_input(
      "From MP / Offset (Min)", value=0.0, step=0.1
  )
  max_mp = st.sidebar.number_input(
      "To MP / Offset (Max)", value=500.0, step=0.1
  )

  filtered_df = df.copy()

  if selected_feature != "All":
    filtered_df = filtered_df[filtered_df["Feature"] == selected_feature]
  if selected_route != "All":
    filtered_df = filtered_df[
        filtered_df["Route"].astype(str) == selected_route
    ]
  if selected_direction != "All":
    filtered_df = filtered_df[
        filtered_df["Direction"].astype(str) == selected_direction
    ]
  if selected_ramp_num != "All":
    filtered_df = filtered_df[
        filtered_df["Ramp #"].astype(str) == selected_ramp_num
    ]
  if selected_ramp_id != "All":
    filtered_df = filtered_df[
        filtered_df["Ramp ID"].astype(str) == selected_ramp_id
    ]

  mp_to_col = "To MP/Offset"
  if mp_from_col in filtered_df.columns and mp_to_col in filtered_df.columns:
    filtered_df[mp_to_col] = pd.to_numeric(
        filtered_df[mp_to_col], errors="coerce"
    )
    filtered_df = filtered_df[
        (filtered_df[mp_from_col] >= min_mp)
        & (filtered_df[mp_to_col] <= max_mp)
    ]

  # Generate links
  filtered_df["FIS Link"] = filtered_df["Asset Id"].apply(
      lambda x: f"https://fis.dot.state.az/Inventory/Asset/ReadOnly?assetId={x}"
  )
  filtered_df["Google Street View"] = filtered_df.apply(
      lambda row: (
          f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={row['Lat']},{row['Long']}"
          if pd.notnull(row["Lat"]) and pd.notnull(row["Long"])
          else None
      ),
      axis=1,
  )
  filtered_df["Google Map Pin"] = filtered_df.apply(
      lambda row: (
          f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Long']}"
          if pd.notnull(row["Lat"]) and pd.notnull(row["Long"])
          else None
      ),
      axis=1,
  )

  display_columns = {
      "Asset Id": "Asset ID",
      "Feature": "Feature",
      "Sub-Feature": "Sub Feature",
      "Route": "Route",
      "Ramp #": "Ramp #",
      "Ramp ID": "Ramp ID",
      "Org": "Org",
      "FIS Link": "FIS Link",
      "Google Street View": "Google Street View",
      "Google Map Pin": "Google Map Pin",
  }

  valid_cols = [
      col for col in display_columns.keys() if col in filtered_df.columns
  ]
  display_df = filtered_df[valid_cols].rename(columns=display_columns)

  st.write(f"**Matching Assets Found:** {len(display_df):,}")
  st.dataframe(
      display_df,
      use_container_width=True,
      column_config={
          "FIS Link": st.column_config.LinkColumn(
              "FIS Link", display_text="Open FIS"
          ),
          "Google Street View": st.column_config.LinkColumn(
              "Google Street View", display_text="Open Street View"
          ),
          "Google Map Pin": st.column_config.LinkColumn(
              "Google Map Pin", display_text="Open Map Pin"
          ),
      },
  )

  csv = filtered_df.to_csv(index=False).encode("utf-8")
  st.download_button(
      label="Download Filtered Results as CSV",
      data=csv,
      file_name="filtered_drainage_assets.csv",
      mime="text/csv",
  )


# ==========================================
# PAGE 2: BATCH ASSET ID LOOKUP & SORT
# ==========================================
elif page == "Batch Asset ID Lookup & Sort":
  st.title("Batch Asset ID Lookup & Route Sort")
  st.markdown(
      "Paste a list of Asset IDs below, click **Run Lookup**, and view a"
      " sequential table alongside an interactive map of all pins."
  )

  with st.form("batch_form"):
    raw_input_ids = st.text_area(
        "Paste Asset IDs (one per line, or separated by commas):",
        height=150,
        placeholder="2972761\n2973153\n2973154",
    )
    submit_button = st.form_submit_button(label="Run Lookup & Sort")

  if submit_button:
    if raw_input_ids.strip():
      import re

      user_ids = re.findall(r"\d+", raw_input_ids)
      user_ids = [int(i) for i in user_ids]

      batch_df = df[df["Asset Id"].isin(user_ids)].copy()

      if len(batch_df) > 0:
        sort_cols = [
            c for c in ["Route", "Direction", mp_from_col] if c in batch_df.columns
        ]
        batch_df = batch_df.sort_values(
            by=sort_cols, ascending=[True, True, True]
        )

        batch_df["FIS Link"] = batch_df["Asset Id"].apply(
            lambda x: (
                f"https://fis.dot.state.az/Inventory/Asset/ReadOnly?assetId={x}"
            )
        )
        batch_df["Google Street View"] = batch_df.apply(
            lambda row: (
                f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={row['Lat']},{row['Long']}"
                if pd.notnull(row["Lat"]) and pd.notnull(row["Long"])
                else None
            ),
            axis=1,
        )
        batch_df["Google Map Pin"] = batch_df.apply(
            lambda row: (
                f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Long']}"
                if pd.notnull(row["Lat"]) and pd.notnull(row["Long"])
                else None
            ),
            axis=1,
        )

        display_columns = {
            "Asset Id": "Asset ID",
            "Feature": "Feature",
            "Sub-Feature": "Sub Feature",
            "Route": "Route",
            "Direction": "Direction",
            "From MP/Offset": "From MP",
            "To MP/Offset": "To MP",
            "Org": "Org",
            "FIS Link": "FIS Link",
            "Google Street View": "Google Street View",
            "Google Map Pin": "Google Map Pin",
        }

        valid_cols = [
            col for col in display_columns.keys() if col in batch_df.columns
        ]
        display_batch_df = batch_df[valid_cols].rename(columns=display_columns)

        st.success(
            f"Successfully matched {len(display_batch_df)} of"
            f" {len(set(user_ids))} entered IDs."
        )

        map_df = batch_df.dropna(subset=["Lat", "Long"]).rename(
            columns={"Lat": "latitude", "Long": "longitude"}
        )
        if len(map_df) > 0:
          st.subheader("Visual Map of Searched Assets")
          st.map(map_df, latitude="latitude", longitude="longitude", zoom=8)

        st.subheader("Sorted Asset List")
        st.dataframe(
            display_batch_df,
            use_container_width=True,
            column_config={
                "FIS Link": st.column_config.LinkColumn(
                    "FIS Link", display_text="Open FIS"
                ),
                "Google Street View": st.column_config.LinkColumn(
                    "Google Street View", display_text="Open Street View"
                ),
                "Google Map Pin": st.column_config.LinkColumn(
                    "Google Map Pin", display_text="Open Map Pin"
                ),
            },
        )

        batch_csv = batch_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Sorted Batch Results as CSV",
            data=batch_csv,
            file_name="sorted_batch_drainage_assets.csv",
            mime="text/csv",
        )
      else:
        st.warning(
            "None of the entered Asset IDs matched records in your database."
        )
    else:
      st.warning("Please paste at least one Asset ID.")


# ==========================================
# PAGE 3: MAP AREA SEARCH (VIEWPORT FILTER)
# ==========================================
elif page == "Map Area Search":
  st.title("Map Area Search")
  st.markdown(
      "Zoom into your target area on the map, then click **Find Assets in Current Map View** "
      "to plot them on the map and generate a list below."
  )

  # 1. Initialize memory
  if "render_center" not in st.session_state:
    st.session_state.render_center = [34.0489, -111.0937]
    st.session_state.render_zoom = 7
  if "live_center" not in st.session_state:
    st.session_state.live_center = [34.0489, -111.0937]
  if "live_zoom" not in st.session_state:
    st.session_state.live_zoom = 7
  if "live_bounds" not in st.session_state:
    st.session_state.live_bounds = {
        "min_lat": 31.33, "max_lat": 37.00,
        "min_lon": -114.82, "max_lon": -109.04
    }
  if "map_assets" not in st.session_state:
    st.session_state.map_assets = pd.DataFrame()
  if "show_request_form" not in st.session_state:
    st.session_state.show_request_form = False

  # 2. Draw map
  m = folium.Map(location=st.session_state.render_center, zoom_start=st.session_state.render_zoom)

  # 3. Add pins
  if not st.session_state.map_assets.empty:
    from folium.plugins import MarkerCluster
    marker_cluster = MarkerCluster().add_to(m)
    plot_df = st.session_state.map_assets.head(3000)
    for _, row in plot_df.iterrows():
      if pd.notnull(row["Lat"]) and pd.notnull(row["Long"]):
        folium.CircleMarker(
            location=[row["Lat"], row["Long"]],
            radius=4,
            color="blue",
            fill=True,
            fill_color="blue",
            tooltip=f"Asset ID: {row.get('Asset Id', 'N/A')}"
        ).add_to(marker_cluster)

  # 4. Display map
  map_data = st_folium(m, width=800, height=500, key="az_map_view", returned_objects=["bounds", "center", "zoom"])

  # 5. Track live position
  if map_data:
    if map_data.get("center"):
      st.session_state.live_center = [map_data["center"]["lat"], map_data["center"]["lng"]]
    if map_data.get("zoom"):
      st.session_state.live_zoom = map_data["zoom"]
    if map_data.get("bounds"):
      b = map_data["bounds"]
      try:
        if isinstance(b, dict):
          lats = [v["lat"] for v in b.values() if isinstance(v, dict) and "lat" in v]
          lons = [v.get("lng", v.get("lon")) for v in b.values() if isinstance(v, dict)]
          if len(lats) == 2 and len(lons) == 2:
            st.session_state.live_bounds = {
                "min_lat": min(lats), "max_lat": max(lats),
                "min_lon": min(lons), "max_lon": max(lons)
            }
        elif isinstance(b, list) and len(b) >= 2:
          st.session_state.live_bounds = {
              "min_lat": min(b[0][0], b[1][0]), "max_lat": max(b[0][0], b[1][0]),
              "min_lon": min(b[0][1], b[1][1]), "max_lon": max(b[0][1], b[1][1])
          }
      except Exception:
        pass

  # 6. Button Logic for searching
  if st.button("Find Assets in Current Map View"):
    st.session_state.show_request_form = False # Hide form on new search
    b = st.session_state.live_bounds
    
    map_filtered_df = df[
        (df["Lat"] >= b["min_lat"]) & (df["Lat"] <= b["max_lat"]) &
        (df["Long"] >= b["min_lon"]) & (df["Long"] <= b["max_lon"])
    ].copy()

    if len(map_filtered_df) > 0:
      st.session_state.map_assets = map_filtered_df
      st.session_state.render_center = st.session_state.live_center
      st.session_state.render_zoom = st.session_state.live_zoom
      st.rerun() 
    else:
      st.session_state.map_assets = pd.DataFrame()
      st.warning("No assets found within this specific map view window.")

  # 7. Render Interactive Data Table and Service Request Form
  if not st.session_state.map_assets.empty:
    display_map_df = st.session_state.map_assets.copy()

    # Add a blank boolean column at the front for checkboxes
    display_map_df.insert(0, "Select", False)

    display_map_df["FIS Link"] = display_map_df["Asset Id"].apply(
        lambda x: f"https://fis.dot.state.az/Inventory/Asset/ReadOnly?assetId={x}"
    )
    display_map_df["Google Street View"] = display_map_df.apply(
        lambda row: (f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={row['Lat']},{row['Long']}"
                     if pd.notnull(row["Lat"]) and pd.notnull(row["Long"]) else None), axis=1
    )
    display_map_df["Google Map Pin"] = display_map_df.apply(
        lambda row: (f"https://www.google.com/maps/search/?api=1&query={row['Lat']},{row['Long']}"
                     if pd.notnull(row["Lat"]) and pd.notnull(row["Long"]) else None), axis=1
    )

    display_columns = {
        "Select": "Select", "Asset Id": "Asset ID", "Feature": "Feature", "Sub-Feature": "Sub Feature",
        "Route": "Route", "Direction": "Direction", "From MP/Offset": "From MP",
        "To MP/Offset": "To MP", "Org": "Org", "FIS Link": "FIS Link",
        "Google Street View": "Google Street View", "Google Map Pin": "Google Map Pin"
    }

    valid_cols = [col for col in display_columns.keys() if col in display_map_df.columns]
    final_df = display_map_df[valid_cols].rename(columns=display_columns)

    st.success(f"Found {len(final_df):,} assets in this map view.")
    
    # Disable all columns from editing EXCEPT the "Select" checkbox column
    disabled_columns = [col for col in final_df.columns if col != "Select"]

    # Use st.data_editor instead of st.dataframe so users can check boxes
    edited_df = st.data_editor(
        final_df,
        use_container_width=True,
        hide_index=True,
        disabled=disabled_columns,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", help="Check to request service", default=False),
            "FIS Link": st.column_config.LinkColumn("FIS Link", display_text="Open FIS"),
            "Google Street View": st.column_config.LinkColumn("Google Street View", display_text="Open Street View"),
            "Google Map Pin": st.column_config.LinkColumn("Google Map Pin", display_text="Open Map Pin"),
        },
    )

    # Filter down to only the rows the user checked
    selected_assets = edited_df[edited_df["Select"] == True]

    # If any assets are checked, show the Request button
    if len(selected_assets) > 0:
      st.markdown("---")
      if st.button(f"Request Services on {len(selected_assets)} Selected Assets", type="primary"):
        st.session_state.show_request_form = True

    # Show the form if the button was clicked
    if st.session_state.show_request_form:
      with st.form("service_request_form"):
        st.subheader("Submit Service Request")
        req_name = st.text_input("Requester's Name")
        req_email = st.text_input("Requester's Email")
        req_unit = st.text_input("Requester's Unit")
        req_notes = st.text_area("Notes")
        
        submitted = st.form_submit_button("Send Email Request")
        
        if submitted:
          if not req_name or not req_email:
            st.error("Please provide at least your Name and Email.")
          else:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Build the email body
            body = f"Requester Name: {req_name}\n"
            body += f"Requester Email: {req_email}\n"
            body += f"Requester Unit: {req_unit}\n\n"
            body += f"Notes:\n{req_notes}\n\n"
            body += "--- Selected Assets ---\n"
            
            for _, row in selected_assets.iterrows():
              body += f"Asset ID: {row['Asset ID']} | Route: {row['Route']} {row['Direction']} | MP: {row['From MP']} | Feature: {row['Feature']}\n"

            # Prepare the email headers
            msg = MIMEMultipart()
            # Fetch login credentials from Streamlit Secrets
            sender_email = st.secrets["EMAIL_USER"]
            sender_password = st.secrets["EMAIL_PASS"]
            
            msg['From'] = sender_email
            msg['To'] = "ErikFurlong@Yahoo.com"
            msg['Subject'] = f"Alert New Service Request From {req_name}"
            msg.attach(MIMEText(body, 'plain'))

            try:
              # Connect to Gmail's server and send
              server = smtplib.SMTP('smtp.gmail.com', 587)
              server.starttls()
              server.login(sender_email, sender_password)
              server.send_message(msg)
              server.quit()
              
              st.success("Your service request has been sent successfully!")
              st.session_state.show_request_form = False # Hide the form after sending
            except Exception as e:
              st.error(f"Failed to send email. Please check your Streamlit Secrets configuration. Error: {e}")

    st.markdown("---")
    map_csv = st.session_state.map_assets.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Map View Results as CSV",
        data=map_csv,
        file_name="map_view_drainage_assets.csv",
        mime="text/csv",
    )
