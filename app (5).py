with st.expander("➕ Add New Opportunity"):
    with st.form("add"):
        title = st.text_input("Title")
        org = st.text_input("Organization")
        cat = st.selectbox("Category", ["Scholarship","Job"])
        deadline = st.date_input("Deadline", value=datetime.today().date()+timedelta(days=30))
        link = st.text_input("Link (optional)")
        description_input = st.text_area("Description (optional)", height=100)

        # ✅ Corrected submit block
        if st.form_submit_button("Add Opportunity"):
            if title and org:
                data = {
                    "title": title,
                    "organization": org,
                    "category": cat,
                    "deadline": deadline,
                    "status": "Not Applied",
                    "description": description_input,
                    "link": link
                }
                add_opportunity(data)
                st.success("Opportunity added!")
                st.rerun()
            else:
                st.warning("Title and Organization are required.")
