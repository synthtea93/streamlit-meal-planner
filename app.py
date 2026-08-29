import pandas as pd
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
  # Fallback empty structure if Google Sheet isn't connected yet
  df = pd.DataFrame(
      columns=["id", "name", "category", "prep_time", "ingredients"]
  )

# --- SIDEBAR: ADD NEW RECIPE ---
with st.sidebar.form("add_recipe_form", clear_on_submit=True):
  st.subheader("➕ Add New Recipe")
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

# --- MAIN LAYOUT: TWO COLUMNS ---
col1, col2 = st.columns([1, 1])

with col1:
  st.header("📖 Select Meals for the Week")

  if df.empty:
    st.info("No recipes found. Add some in the sidebar to get started!")
    selected_recipes = []
  else:
    # Multiselect widget for choosing recipes
    recipe_names = df["name"].tolist()
    selected_recipes = st.multiselect(
        "Choose recipes to plan your week:",
        options=recipe_names,
        placeholder="Select recipes...",
    )

    # Show selected recipe details
    if selected_recipes:
      st.subheader("Selected Recipes Summary")
      selected_df = df[df["name"].isin(selected_recipes)]
      for _, row in selected_df.iterrows():
        with st.expander(f"📌 {row['name']} ({row['category']})"):
          st.write(f"**Prep Time:** {row['prep_time']}")
          st.write(f"**Ingredients:** {row['ingredients']}")

with col2:
  st.header("🛒 Combined Grocery List")

  if not selected_recipes:
    st.info("👈 Select one or more recipes on the left to build your grocery list.")
  else:
    # Extract, clean, and deduplicate ingredients
    selected_df = df[df["name"].isin(selected_recipes)]
    raw_ingredients = []

    for item_string in selected_df["ingredients"].dropna():
      # Split on commas and strip leading/trailing whitespace
      items = [i.strip() for i in str(item_string).split(",") if i.strip()]
      raw_ingredients.extend(items)

    # Remove duplicates while preserving list order
    unique_ingredients = list(dict.fromkeys(raw_ingredients))

    st.write(f"**Total Items:** {len(unique_ingredients)}")

    # Copyable text code-block for fast mobile clipboard copying
    formatted_text_list = "\n".join([f"- {item}" for item in unique_ingredients])
    st.code(formatted_text_list, language="text")

    st.markdown("---")
    st.subheader("Interactive Checklist")

    # Interactive checkable list for shopping
    checked_items = []
    for idx, item in enumerate(unique_ingredients):
      # Create interactive checkbox for each ingredient
      is_checked = st.checkbox(item, key=f"ing_{idx}")
      if is_checked:
        checked_items.append(item)

    if checked_items:
      st.caption(
          f"Completed {len(checked_items)} of {len(unique_ingredients)} items!"
      )