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
tab1, tab2 = st.tabs(["📅 Weekly Schedule", "🛒 Combined Grocery List"])

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
  st.header("🗓️ Plan Your Meals for the Week")

  if df.empty:
    st.info("No recipes found in your database yet. Add some in the sidebar!")
  else:
    # Initialize weekly schedule session state
    if "weekly_schedule" not in st.session_state:
      st.session_state.weekly_schedule = {day: "None" for day in DAYS}

    # Dropdowns for each day of the week
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

    # Display recipe breakdown for assigned days
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

  # Get list of unique meals scheduled across the week
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

    # Fast clipboard copying block
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