import pandas as pd
from recipe_scrapers import scrape_me
import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(
    page_title="Meal Planner & Grocery List", page_icon="🥗", layout="wide"
)

st.title("🥗 Weekly Meal Planner & Grocery List")

# Establish connection to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)


# Function to fetch all recipes
def load_recipes():
  return conn.read(worksheet="Recipes", ttl="0")


try:
  df = load_recipes()
except Exception:
  df = pd.DataFrame(
      columns=["id", "name", "category", "prep_time", "ingredients"]
  )

# --- SIDEBAR: RECIPE MANAGEMENT ---
st.sidebar.subheader("🔗 Import Recipe from Web")
url_input = st.sidebar.text_input(
    "Paste Recipe URL", placeholder="https://..."
)

if st.sidebar.button("Fetch & Save Recipe"):
  if url_input:
    try:
      with st.spinner("Scraping recipe details..."):
        scraper = scrape_me(url_input)
        title = scraper.title()
        prep_time = (
            f"{scraper.total_time()} mins"
            if scraper.total_time()
            else "20 mins"
        )
        ingredients_list = ", ".join(scraper.ingredients())

        new_id = len(df) + 1
        new_data = pd.DataFrame([{
            "id": new_id,
            "name": title,
            "category": "Dinner",
            "prep_time": prep_time,
            "ingredients": ingredients_list,
        }])

        updated_df = pd.concat([df, new_data], ignore_index=True)
        conn.update(worksheet="Recipes", data=updated_df)
        st.sidebar.success(f"Successfully imported '{title}'!")
        st.rerun()
    except Exception:
      st.sidebar.error("Could not scrape that website. Add it manually below.")

st.sidebar.markdown("---")

# Manual recipe entry form
with st.sidebar.form("add_recipe_form", clear_on_submit=True):
  st.subheader("➕ Add Recipe Manually")
  name = st.text_input("Recipe Name")
  category = st.selectbox(
      "Category", ["Breakfast", "Lunch", "Dinner", "Snack"]
  )
  prep_time = st.text_input("Prep Time", "20 mins")
  ingredients_input = st.text_area(
      "Ingredients (comma-separated)",
      placeholder="Ground Beef, Tortillas, Salsa, Cheese",
  )

  submitted = st.form_submit_button("Save Recipe")

  if submitted and name and ingredients_input:
    new_id = len(df) + 1
    new_data = pd.DataFrame([{
        "id": new_id,
        "name": name,
        "category": category,
        "prep_time": prep_time,
        "ingredients": ingredients_input,
    }])
    updated_df = pd.concat([df, new_data], ignore_index=True)
    conn.update(worksheet="Recipes", data=updated_df)
    st.success(f"Added '{name}'!")
    st.rerun()

# --- MAIN APP TABS ---
tab1, tab2, tab3 = st.tabs(
    ["📅 Weekly Schedule", "🛒 Combined Grocery List", "📚 Recipe Book"]
)

DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
recipe_options = ["None"] + df["name"].tolist() if not df.empty else ["None"]

# --- TAB 1: WEEKLY PLANNER ---
with tab1:
  col_title, col_btn = st.columns([3, 1])
  with col_title:
    st.header("🗓️ Plan Your Meals for the Week")
  with col_btn:
    st.write("")
    if st.button("🔄 Clear Weekly Schedule", use_container_width=True):
      if "weekly_schedule" in st.session_state:
        for day in DAYS:
          st.session_state.weekly_schedule[day] = "None"
      st.rerun()

  if df.empty:
    st.info("No recipes found in your database yet. Add some in the sidebar!")
  else:
    if "weekly_schedule" not in st.session_state:
      st.session_state.weekly_schedule = {day: "None" for day in DAYS}

    cols = st.columns(7)
    for idx, day in enumerate(DAYS):
      with cols[idx]:
        st.subheader(day)
        selected_meal = st.selectbox(
            f"Select for {day}",
            options=recipe_options,
            index=recipe_options.index(
                st.session_state.weekly_schedule.get(day, "None")
            )
            if st.session_state.weekly_schedule.get(day, "None")
            in recipe_options
            else 0,
            key=f"select_{day}",
            label_visibility="collapsed",
        )
        st.session_state.weekly_schedule[day] = selected_meal

    st.markdown("---")
    st.subheader("📋 Scheduled Week Overview")

    scheduled_days = {
        day: meal
        for day, meal in st.session_state.weekly_schedule.items()
        if meal != "None"
    }

    if not scheduled_days:
      st.info("Select meals from the day menus above to populate your weekly plan.")
    else:
      for day, meal in scheduled_days.items():
        recipe_row = df[df["name"] == meal]
        if not recipe_row.empty:
          prep_time = recipe_row.iloc[0]["prep_time"]
          ingredients = recipe_row.iloc[0]["ingredients"]
          with st.expander(f"📌 {day}: {meal} ({prep_time})"):
            st.write(f"**Ingredients:** {ingredients}")

# --- TAB 2: GROCERY LIST GENERATOR ---
with tab2:
  st.header("🛒 Combined Grocery List")

  scheduled_meals = list(
      set([
          meal
          for meal in st.session_state.get(
              "weekly_schedule", {}
          ).values()
          if meal != "None"
      ])
  )

  if not scheduled_meals:
    st.info(
        "👈 Go to the **Weekly Schedule** tab and assign meals to your week first!"
    )
  else:
    selected_df = df[df["name"].isin(scheduled_meals)]
    raw_ingredients = []

    for item_string in selected_df["ingredients"].dropna():
      items = [i.strip() for i in str(item_string).split(",") if i.strip()]
      raw_ingredients.extend(items)

    unique_ingredients = list(dict.fromkeys(raw_ingredients))

    st.write(
        f"**Planned Meals:** {', '.join(scheduled_meals)} | **Total Unique"
        f" Items:** {len(unique_ingredients)}"
    )

    formatted_text_list = "\n".join(
        [f"- {item}" for item in unique_ingredients]
    )
    st.code(formatted_text_list, language="text")

    st.markdown("---")
    st.subheader("Interactive Checklist")

    checked_items = []
    for idx, item in enumerate(unique_ingredients):
      is_checked = st.checkbox(item, key=f"ing_sched_{idx}")
      if is_checked:
        checked_items.append(item)

    if checked_items:
      st.caption(
          f"Completed {len(checked_items)} of {len(unique_ingredients)} items!"
      )

# --- TAB 3: RECIPE BOOK ---
with tab3:
  st.header("📚 Recipe Book")

  if df.empty:
    st.info("No recipes stored in your Google Sheet yet.")
  else:
    col_search, col_filter = st.columns([2, 1])

    with col_search:
      search_term = st.text_input(
          "🔍 Search recipes by name or ingredient",
          placeholder="Type to search...",
      )

    with col_filter:
      categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
      category_filter = st.selectbox("Filter by Category", options=categories)

    filtered_df = df.copy()

    if category_filter != "All":
      filtered_df = filtered_df[filtered_df["category"] == category_filter]

    if search_term:
      search_lower = search_term.lower()
      filtered_df = filtered_df[
          filtered_df["name"]
          .astype(str)
          .str.lower()
          .str.contains(search_lower)
          | filtered_df["ingredients"]
          .astype(str)
          .str.lower()
          .str.contains(search_lower)
      ]

    st.write(f"**Showing {len(filtered_df)} of {len(df)} recipes**")
    st.markdown("---")

    # Track editing state across reruns
    if "editing_id" not in st.session_state:
      st.session_state.editing_id = None

    for idx, row in filtered_df.iterrows():
      rec_id = row["id"]
      with st.expander(
          f"🍲 **{row['name']}** | {row.get('category', 'Dinner')} | ⏱️"
          f" {row.get('prep_time', '20 mins')}"
      ):
        # Display normal view if not currently editing this recipe
        if st.session_state.editing_id != rec_id:
          st.write("**Ingredients:**")
          ingredients_list = [
              i.strip()
              for i in str(row["ingredients"]).split(",")
              if i.strip()
          ]
          for ing in ingredients_list:
            st.write(f"- {ing}")

          st.markdown("---")

          btn_col1, btn_col2 = st.columns([1, 1])
          with btn_col1:
            if st.button("✏️ Edit Recipe", key=f"edit_btn_{rec_id}"):
              st.session_state.editing_id = rec_id
              st.rerun()

          with btn_col2:
            if st.button("🗑️ Delete Recipe", key=f"del_{rec_id}"):
              updated_df = df[df["id"] != rec_id].reset_index(drop=True)
              conn.update(worksheet="Recipes", data=updated_df)
              st.success(f"Deleted '{row['name']}'!")
              st.rerun()

        # Display editable form if editing this recipe
        else:
          st.subheader("Edit Recipe Details")
          with st.form(key=f"edit_form_{rec_id}"):
            edit_name = st.text_input("Recipe Name", value=row["name"])
            category_options = ["Breakfast", "Lunch", "Dinner", "Snack"]
            current_cat = row.get("category", "Dinner")
            cat_idx = (
                category_options.index(current_cat)
                if current_cat in category_options
                else 2
            )
            edit_category = st.selectbox(
                "Category", options=category_options, index=cat_idx
            )
            edit_prep_time = st.text_input(
                "Prep Time", value=row.get("prep_time", "20 mins")
            )
            edit_ingredients = st.text_area(
                "Ingredients (comma-separated)", value=row["ingredients"]
            )

            save_col, cancel_col = st.columns([1, 1])
            with save_col:
              save_submitted = st.form_submit_button("💾 Save Changes")
            with cancel_col:
              cancel_submitted = st.form_submit_button("❌ Cancel")

            if save_submitted:
              # Update dataframe row by ID
              df.loc[df["id"] == rec_id, "name"] = edit_name
              df.loc[df["id"] == rec_id, "category"] = edit_category
              df.loc[df["id"] == rec_id, "prep_time"] = edit_prep_time
              df.loc[df["id"] == rec_id, "ingredients"] = edit_ingredients

              # Sync back to Google Sheet
              conn.update(worksheet="Recipes", data=df)
              st.session_state.editing_id = None
              st.success("Recipe updated successfully!")
              st.rerun()

            if cancel_submitted:
              st.session_state.editing_id = None
              st.rerun()