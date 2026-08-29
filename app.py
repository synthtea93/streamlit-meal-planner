import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from recipe_scrapers import scrape_me

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Recipe Book & Meal Planner", layout="wide", page_icon="🍳")
st.title("🍳 Recipe Book & Meal Planner")

# --- INITIALIZE GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- LOAD DATA FUNCTIONS ---
def load_recipes():
    # ttl=0 forces Streamlit to bypass local cache and get fresh data
    return conn.read(worksheet="Recipes", ttl=0)

def load_meal_plan():
    return conn.read(worksheet="MealPlan", ttl=0)

# Fetch data with fallbacks for missing sheets or empty structures
try:
    df_recipes = load_recipes()
except Exception:
    df_recipes = pd.DataFrame(columns=["id", "name", "category", "prep_time", "ingredients"])

try:
    df_plan = load_meal_plan()
except Exception:
    df_plan = pd.DataFrame(columns=["day", "meal_type", "recipe_id", "recipe_name"])

# Normalize ID types for seamless joining/filtering
if not df_recipes.empty and "id" in df_recipes.columns:
    df_recipes["id"] = df_recipes["id"].astype(str)

if not df_plan.empty and "recipe_id" in df_plan.columns:
    df_plan["recipe_id"] = df_plan["recipe_id"].astype(str)


# --- SIDEBAR: ADD RECIPES ---
st.sidebar.header("➕ Add New Recipe")

# --- OPTION A: IMPORT FROM URL ---
with st.sidebar.expander("🌐 Import from Website URL", expanded=True):
    with st.form("import_url_form", clear_on_submit=True):
        recipe_url = st.text_input("Recipe Web Link", placeholder="https://www.allrecipes.com/recipe/...")
        url_category = st.selectbox("Category", ["Breakfast", "Lunch", "Dinner", "Snack"], key="url_cat")
        submit_url = st.form_submit_button("Import & Save")

        if submit_url:
            if not recipe_url.strip():
                st.sidebar.error("Please enter a URL.")
            else:
                try:
                    scraper = scrape_me(recipe_url)
                    scraped_title = scraper.title()
                    scraped_time = f"{scraper.total_time()} mins" if scraper.total_time() else "20 mins"
                    
                    # Extract list of ingredients and join with commas
                    raw_ings = scraper.ingredients()
                    scraped_ingredients = ", ".join(raw_ings) if raw_ings else ""

                    next_id = str(len(df_recipes) + 1)
                    
                    new_row = pd.DataFrame([{
                        "id": next_id,
                        "name": scraped_title,
                        "category": url_category,
                        "prep_time": scraped_time,
                        "ingredients": scraped_ingredients
                    }])

                    updated_recipes = pd.concat([df_recipes, new_row], ignore_index=True)
                    conn.update(worksheet="Recipes", data=updated_recipes)
                    st.cache_data.clear()
                    st.sidebar.success(f"Imported '{scraped_title}'!")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Could not scrape recipe: {e}")

# --- OPTION B: MANUAL ENTRY FORM ---
with st.sidebar.expander("✏️ Add Manually", expanded=False):
    with st.form("add_recipe_form", clear_on_submit=True):
        name = st.text_input("Recipe Name")
        category = st.selectbox("Category", ["Breakfast", "Lunch", "Dinner", "Snack"], key="manual_cat")
        prep_time = st.text_input("Prep Time", "20 mins")
        
        # Optional ingredients field
        ingredients_input = st.text_area(
            "Ingredients (Optional, comma-separated)",
            placeholder="e.g. Ground Beef, Tortillas, Salsa, Cheese"
        )

        submitted = st.form_submit_button("Save Manual Recipe")

        if submitted:
            if not name.strip():
                st.sidebar.error("Please enter a Recipe Name.")
            else:
                try:
                    next_id = str(len(df_recipes) + 1)
                    clean_ingredients = ingredients_input.strip() if ingredients_input else ""

                    new_row = pd.DataFrame([{
                        "id": next_id,
                        "name": name.strip(),
                        "category": category,
                        "prep_time": prep_time.strip(),
                        "ingredients": clean_ingredients
                    }])

                    updated_recipes = pd.concat([df_recipes, new_row], ignore_index=True)
                    conn.update(worksheet="Recipes", data=updated_recipes)
                    st.cache_data.clear()
                    st.sidebar.success(f"Added '{name.strip()}'!")
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Error saving to Google Sheets: {e}")


# --- MAIN TABS ---
tab_recipes, tab_planner, tab_groceries = st.tabs(["📖 Recipe Book", "📅 Weekly Meal Planner", "🛒 Shopping List"])

# --- TAB 1: RECIPE BOOK ---
with tab_recipes:
    st.header("Recipe Collection")
    
    if df_recipes.empty:
        st.info("No recipes found in your Google Sheet yet. Add one from the sidebar!")
    else:
        # Search & Filter
        col1, col2 = st.columns([2, 1])
        with col1:
            search_query = st.text_input("🔍 Search recipes or ingredients:", "")
        with col2:
            cat_filter = st.selectbox("Filter Category", ["All"] + list(df_recipes["category"].unique()))

        filtered_df = df_recipes.copy()

        if search_query:
            filtered_df = filtered_df[
                filtered_df["name"].str.contains(search_query, case=False, na=False) |
                filtered_df["ingredients"].str.contains(search_query, case=False, na=False)
            ]

        if cat_filter != "All":
            filtered_df = filtered_df[filtered_df["category"] == cat_filter]

        # Display Expanders
        for idx, row in filtered_df.iterrows():
            with st.expander(f"**{row['name']}** ({row['category']}) - ⏱️ {row['prep_time']}"):
                st.write("**Ingredients:**")
                if row["ingredients"]:
                    ing_list = [i.strip() for i in str(row["ingredients"]).split(",") if i.strip()]
                    for ing in ing_list:
                        st.write(f"- {ing}")
                else:
                    st.write("*No ingredients specified.*")


# --- TAB 2: WEEKLY MEAL PLANNER ---
with tab_planner:
    st.header("Weekly Schedule")
    
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meal_types = ["Breakfast", "Lunch", "Dinner"]

    if df_recipes.empty:
        st.warning("Please add some recipes to your Recipe Book before setting up a meal plan.")
    else:
        recipe_options = {"None": ""}
        for _, r in df_recipes.iterrows():
            recipe_options[r["name"]] = r["id"]

        with st.form("meal_plan_form"):
            st.subheader("Assign Meals")
            
            cols = st.columns(3)
            updated_plan_rows = []

            for i, day in enumerate(days):
                col = cols[i % 3]
                with col:
                    st.markdown(f"### {day}")
                    for m_type in meal_types:
                        existing_val = "None"
                        if not df_plan.empty:
                            match = df_plan[(df_plan["day"] == day) & (df_plan["meal_type"] == m_type)]
                            if not match.empty:
                                existing_val = match.iloc[0]["recipe_name"]

                        selected_recipe = st.selectbox(
                            f"{m_type}",
                            options=list(recipe_options.keys()),
                            index=list(recipe_options.keys()).index(existing_val) if existing_val in recipe_options else 0,
                            key=f"{day}_{m_type}"
                        )

                        if selected_recipe != "None":
                            updated_plan_rows.append({
                                "day": day,
                                "meal_type": m_type,
                                "recipe_id": recipe_options[selected_recipe],
                                "recipe_name": selected_recipe
                            })

            save_plan = st.form_submit_button("Save Meal Plan")

            if save_plan:
                try:
                    new_plan_df = pd.DataFrame(updated_plan_rows)
                    conn.update(worksheet="MealPlan", data=new_plan_df)
                    st.cache_data.clear()
                    st.success("Meal plan updated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving meal plan: {e}")


# --- TAB 3: GENERATED SHOPPING LIST ---
with tab_groceries:
    st.header("Auto-Generated Shopping List")

    if df_plan.empty:
        st.info("Your meal plan is currently empty. Assign recipes in the Planner tab to see your grocery list.")
    else:
        merged = pd.merge(df_plan, df_recipes, left_on="recipe_id", right_on="id", how="inner")

        all_ingredients = []
        for raw_ing in merged["ingredients"].dropna():
            if raw_ing:
                items = [i.strip().capitalize() for i in str(raw_ing).split(",") if i.strip()]
                all_ingredients.extend(items)

        if not all_ingredients:
            st.write("No ingredients required for your planned meals!")
        else:
            ing_counts = pd.Series(all_ingredients).value_counts()

            st.subheader("Items to Buy:")
            for ing, count in ing_counts.items():
                qty_str = f" (x{count})" if count > 1 else ""
                st.checkbox(f"{ing}{qty_str}", key=f"shop_{ing}")