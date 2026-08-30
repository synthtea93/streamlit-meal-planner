import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Digital Recipes & Meal Planning", layout="wide", page_icon="🗂️")
st.title("🗂️ Digital Recipes & Meal Planning")

# --- INITIALIZE GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_recipes():
    return conn.read(worksheet="Recipes", ttl=0)

def load_meal_plan():
    return conn.read(worksheet="MealPlan", ttl=0)

try:
    df_recipes = load_recipes()
except Exception:
    df_recipes = pd.DataFrame(columns=[
        "id", "name", "category", "total_time", "ingredients", "instructions", 
        "tags", "date_added"
    ])

# Ensure required columns exist for existing Google Sheets
for col in ["instructions", "tags", "date_added"]:
    if col not in df_recipes.columns:
        df_recipes[col] = ""

try:
    df_plan = load_meal_plan()
except Exception:
    df_plan = pd.DataFrame(columns=["day", "meal_type", "recipe_id", "recipe_name"])

if not df_recipes.empty and "id" in df_recipes.columns:
    df_recipes["id"] = df_recipes["id"].astype(str)

if not df_plan.empty and "recipe_id" in df_plan.columns:
    df_plan["recipe_id"] = df_plan["recipe_id"].astype(str)


# --- SIDEBAR: ADD RECIPES ---
st.sidebar.header("➕ Add New Index Card")

with st.sidebar.form("add_recipe_form", clear_on_submit=True):
    name = st.text_input("Recipe Name", placeholder="e.g. Garlic Butter Chicken")
    category = st.selectbox("Category", ["Breakfast", "Lunch", "Dinner", "Sides", "Snack"], key="manual_cat")
    prep_time = st.text_input("Prep Time", "20 mins")
    
    tags_input = st.text_input("Tags (Comma-separated)", placeholder="e.g. Quick, High-Protein, Kid-Friendly")
    
    ingredients_input = st.text_area(
        "Ingredients (Paste list or line-by-line)",
        placeholder="1 lb Chicken Breast\n2 tbsp Butter\n3 cloves Garlic",
        height=120
    )

    instructions_input = st.text_area(
        "Instructions / Notes (Optional)",
        placeholder="1. Sear chicken in butter.\n2. Add garlic and simmer.",
        height=120
    )

    submitted = st.form_submit_button("Save Index Card")

    if submitted:
        if not name.strip():
            st.sidebar.error("Please enter a Recipe Name.")
        else:
            try:
                next_id = str(len(df_recipes) + 1)
                today_str = datetime.now().strftime("%Y-%m-%d")

                if ingredients_input:
                    lines = [line.strip() for line in ingredients_input.split("\n") if line.strip()]
                    clean_ingredients = ", ".join(lines)
                else:
                    clean_ingredients = ""

                clean_instructions = instructions_input.strip() if instructions_input else ""
                clean_tags = ", ".join([t.strip() for t in tags_input.split(",") if t.strip()]) if tags_input else ""

                new_row_data = {
                    "id": next_id,
                    "name": name.strip(),
                    "category": category,
                    "prep_time": prep_time.strip(),
                    "ingredients": clean_ingredients,
                    "instructions": clean_instructions,
                    "tags": clean_tags,
                    "date_added": today_str
                }
                
                # Keep column compatibility if image_url exists in sheet
                if "image_url" in df_recipes.columns:
                    new_row_data["image_url"] = ""

                new_row = pd.DataFrame([new_row_data])

                updated_recipes = pd.concat([df_recipes, new_row], ignore_index=True)
                conn.update(worksheet="Recipes", data=updated_recipes)
                st.cache_data.clear()
                st.sidebar.success(f"Added '{name.strip()}'!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error saving to Google Sheets: {e}")


# --- MAIN TABS ---
tab_recipes, tab_planner, tab_groceries = st.tabs(["🗂️ Recipe Box", "📅 Weekly Meal Planner", "🛒 Shopping List"])

# --- TAB 1: RECIPE BOX (INDEX CARDS) ---
with tab_recipes:
    st.header("Recipe Index Box")
    
    if df_recipes.empty:
        st.info("Your recipe box is empty. Add a recipe card from the sidebar!")
    else:
        # Search & Filters Controls
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            search_query = st.text_input("🔍 Search title, ingredients, instructions, or tags:", "")
        
        with c2:
            available_cats = ["Breakfast", "Lunch", "Dinner", "Snack"]
            cat_filter = st.selectbox("Category Filter", ["All"] + available_cats)
        
        all_tags_set = set()
        for raw_t in df_recipes["tags"].dropna():
            if raw_t:
                all_tags_set.update([t.strip() for t in str(raw_t).split(",") if t.strip()])
        
        with c3:
            tag_filter = st.selectbox("Tag Filter", ["All"] + sorted(list(all_tags_set)))
        with c4:
            sort_by = st.selectbox("Sort By", ["A-Z", "Z-A", "Newest First", "Oldest First", "Quickest Prep"])

        filtered_df = df_recipes.copy()

        # Text search
        if search_query:
            filtered_df = filtered_df[
                filtered_df["name"].str.contains(search_query, case=False, na=False) |
                filtered_df["ingredients"].str.contains(search_query, case=False, na=False) |
                filtered_df["instructions"].str.contains(search_query, case=False, na=False) |
                filtered_df["tags"].str.contains(search_query, case=False, na=False)
            ]

        # Category filter
        if cat_filter != "All":
            filtered_df = filtered_df[filtered_df["category"] == cat_filter]

        # Tag filter
        if tag_filter != "All":
            filtered_df = filtered_df[filtered_df["tags"].str.contains(tag_filter, case=False, na=False)]

        # Sorting logic
        if sort_by == "A-Z":
            filtered_df = filtered_df.sort_values(by="name", key=lambda x: x.str.lower(), ascending=True)
        elif sort_by == "Z-A":
            filtered_df = filtered_df.sort_values(by="name", key=lambda x: x.str.lower(), ascending=False)
        elif sort_by == "Newest First":
            filtered_df = filtered_df.sort_values(by="date_added", ascending=False)
        elif sort_by == "Oldest First":
            filtered_df = filtered_df.sort_values(by="date_added", ascending=True)
        elif sort_by == "Quickest Prep":
            filtered_df["prep_num"] = filtered_df["prep_time"].str.extract(r'(\d+)').astype(float).fillna(999)
            filtered_df = filtered_df.sort_values(by="prep_num", ascending=True).drop(columns=["prep_num"])

        # Display Cards
        for idx, row in filtered_df.iterrows():
            card_id = str(row["id"])
            tag_display = f" | 🏷️ {row['tags']}" if pd.notna(row["tags"]) and str(row["tags"]).strip() else ""
            
            with st.expander(f"📌 **{row['name']}** ({row['category']}) — ⏱️ {row['prep_time']}{tag_display}"):
                view_tab, edit_tab = st.tabs(["👁️ View Card", "✏️ Edit / Delete"])
                
                # VIEW TAB
                with view_tab:
                    card_col1, card_col2 = st.columns(2)
                    
                    with card_col1:
                        st.markdown("#### 🛒 Ingredients")
                        if pd.notna(row["ingredients"]) and str(row["ingredients"]).strip():
                            ing_list = [i.strip() for i in str(row["ingredients"]).split(",") if i.strip()]
                            for ing in ing_list:
                                st.write(f"• {ing}")
                        else:
                            st.caption("*No ingredients listed.*")

                    with card_col2:
                        st.markdown("#### 📝 Instructions / Notes")
                        if pd.notna(row["instructions"]) and str(row["instructions"]).strip():
                            st.write(row["instructions"])
                        else:
                            st.caption("*No instructions listed.*")
                    
                    if pd.notna(row["date_added"]) and str(row["date_added"]).strip():
                        st.caption(f"📅 Added on: {row['date_added']}")

                # EDIT TAB
                with edit_tab:
                    st.markdown("##### ✏️ Update Recipe Information")
                    edit_name = st.text_input("Recipe Name", value=row["name"], key=f"name_{card_id}")
                    
                    cat_options = ["Breakfast", "Lunch", "Dinner", "Sides", "Snack"]
                    current_cat_idx = cat_options.index(row["category"]) if row["category"] in cat_options else 0
                    edit_category = st.selectbox("Category", cat_options, index=current_cat_idx, key=f"cat_{card_id}")
                    
                    edit_prep = st.text_input("Prep Time", value=str(row["prep_time"]), key=f"prep_{card_id}")
                    
                    edit_tags = st.text_input(
                        "Tags (Comma-separated)", 
                        value=str(row["tags"]) if pd.notna(row["tags"]) else "", 
                        key=f"tags_{card_id}"
                    )

                    edit_ingredients = st.text_area(
                        "Ingredients (Optional, comma-separated)", 
                        value=str(row["ingredients"]) if pd.notna(row["ingredients"]) else "", 
                        key=f"ing_{card_id}"
                    )
                    
                    edit_instructions = st.text_area(
                        "Instructions / Notes (Optional)", 
                        value=str(row["instructions"]) if pd.notna(row["instructions"]) else "", 
                        key=f"inst_{card_id}"
                    )
                    
                    col_save, col_del = st.columns([1, 1])
                    
                    with col_save:
                        if st.button("💾 Save Changes", key=f"save_btn_{card_id}"):
                            try:
                                row_idx = df_recipes[df_recipes["id"].astype(str) == card_id].index
                                if not row_idx.empty:
                                    target_i = row_idx[0]
                                    
                                    df_recipes.at[target_i, "name"] = edit_name.strip()
                                    df_recipes.at[target_i, "category"] = edit_category
                                    df_recipes.at[target_i, "prep_time"] = edit_prep.strip()
                                    df_recipes.at[target_i, "tags"] = edit_tags.strip()
                                    df_recipes.at[target_i, "ingredients"] = edit_ingredients.strip()
                                    df_recipes.at[target_i, "instructions"] = edit_instructions.strip()

                                    conn.update(worksheet="Recipes", data=df_recipes)
                                    st.cache_data.clear()
                                    st.success(f"Updated '{edit_name}'!")
                                    st.rerun()
                                else:
                                    st.error("Could not locate recipe in sheet.")
                            except Exception as e:
                                st.error(f"Error updating recipe: {e}")

                    with col_del:
                        if st.button("🗑️ Delete Card", key=f"del_btn_{card_id}"):
                            try:
                                updated_df = df_recipes[df_recipes["id"].astype(str) != card_id]
                                conn.update(worksheet="Recipes", data=updated_df)
                                st.cache_data.clear()
                                st.success(f"Deleted '{row['name']}'!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting card: {e}")


# --- TAB 2: WEEKLY MEAL PLANNER ---
with tab_planner:
    st.header("Weekly Schedule")
    
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meal_types = ["Breakfast", "Lunch", "Dinner", "Sides", "Snack"]

    if df_recipes.empty:
        st.warning("Please add some recipe cards before setting up a meal plan.")
    else:
        recipe_options = {"None": ""}
        for _, r in df_recipes.iterrows():
            recipe_options[r["name"]] = r["id"]

        with st.form("meal_plan_form"):
            st.subheader("Assign Meals")
            
            updated_plan_rows = []

            for i in range(0, len(days), 3):
                day_chunk = days[i:i+3]
                cols = st.columns(3)
                
                for j, day in enumerate(day_chunk):
                    with cols[j]:
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

            save_plan = st.form_submit_button("💾 Save Meal Plan")

            if save_plan:
                try:
                    if updated_plan_rows:
                        new_plan_df = pd.DataFrame(updated_plan_rows)
                    else:
                        new_plan_df = pd.DataFrame(columns=["day", "meal_type", "recipe_id", "recipe_name"])

                    new_plan_df = new_plan_df[["day", "meal_type", "recipe_id", "recipe_name"]]

                    conn.update(worksheet="MealPlan", data=new_plan_df)
                    st.cache_data.clear()
                    st.success("Meal plan updated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving meal plan: {e}")

        st.write("")
        if st.button("🗑️ Clear Entire Weekly Plan"):
            try:
                for day in days:
                    for m_type in meal_types:
                        key = f"{day}_{m_type}"
                        if key in st.session_state:
                            del st.session_state[key]

                empty_plan_df = pd.DataFrame(columns=["day", "meal_type", "recipe_id", "recipe_name"])
                conn.update(worksheet="MealPlan", data=empty_plan_df)
                st.cache_data.clear()
                
                st.success("Weekly meal plan and dropdowns cleared!")
                st.rerun()
            except Exception as e:
                st.error(f"Error clearing meal plan: {e}")

        st.divider()
        st.subheader("🖨️ Share & Print Weekly Plan")

        if df_plan.empty:
            st.caption("No meals planned yet for this week.")
        else:
            df_plan_sorted = df_plan.copy()
            df_plan_sorted["day"] = pd.Categorical(df_plan_sorted["day"], categories=days, ordered=True)
            df_plan_sorted = df_plan_sorted.sort_values("day")

            pivot_plan = df_plan_sorted.pivot(index="day", columns="meal_type", values="recipe_name").fillna("-")

            for m in meal_types:
                if m not in pivot_plan.columns:
                    pivot_plan[m] = "-"
            pivot_plan = pivot_plan[meal_types]

            st.markdown("#### Weekly Overview")
            st.dataframe(pivot_plan, width="stretch")

            csv_data = pivot_plan.to_csv().encode('utf-8')
            
            st.download_button(
                label="📥 Download Plan as CSV",
                data=csv_data,
                file_name="weekly_meal_plan.csv",
                mime="text/csv"
            )


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