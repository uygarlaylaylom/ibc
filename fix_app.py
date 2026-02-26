import sys
with open('app.py', 'r') as f:
    lines = f.readlines()

new_lines = []
in_tab1 = False
for i, line in enumerate(lines):
    if "with tab1:" in line and "# TAB 1: Notes & Intelligence" in lines[i-1]:
        new_lines.append(line)
        new_lines.append("                    @st.experimental_fragment\n")
        new_lines.append("                    def render_notes_fragment(comp):\n")
        in_tab1 = True
        continue
        
    if in_tab1:
        if "with tab2:" in line and "TAB 2: Attachments" in lines[i-1]:
            in_tab1 = False
            # Before closing tab1 context, call the function
            new_lines.insert(-1, "                    render_notes_fragment(comp)\n\n")
            new_lines.append(line)
        else:
            # Indent
            if line.strip() == "":
                new_lines.append(line)
            else:
                new_lines.append("    " + line)
    else:
        new_lines.append(line)

with open('app.py', 'w') as f:
    f.writelines(new_lines)

print("Done")
