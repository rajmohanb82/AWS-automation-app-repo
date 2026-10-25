from fpdf import FPDF
from datetime import datetime, timezone
import tempfile
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

class AWSReport(FPDF):
    def header(self):
        # Logo placeholder (colored rectangle)
        self.set_fill_color(35, 47, 62) # AWS Dark Blue
        self.rect(0, 0, 210, 40, 'F')
        
        self.set_font('Helvetica', 'B', 24)
        self.set_text_color(255, 255, 255)
        self.cell(0, 20, self.report_title, ln=True, align='C')
        
        self.set_font('Helvetica', 'I', 10)
        self.cell(0, 10, f"Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Confidential AWS infrastructure Report', align='C')

def generate_cost_report(scan_data, advice_data, profile, region):
    pdf = AWSReport()
    pdf.report_title = "AWS Cost Optimization Report"
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Summary Section
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(35, 47, 62)
    pdf.cell(0, 10, "Executive Summary", ln=True)
    pdf.ln(5)
    
    # 3-column summary boxes
    pdf.set_font('Helvetica', '', 11)
    pdf.set_fill_color(240, 242, 245)
    
    col_width = 55
    actual_ce = scan_data.get('actual_30d_ce_cost', scan_data.get('total_cost', 0))
    
    pdf.cell(col_width, 20, f"Actual 30d Bill: ${actual_ce:.2f}", border=1, align='C', fill=True)
    pdf.cell(5)
    pdf.set_text_color(40, 167, 69) # Green
    pdf.cell(col_width, 20, f"Potential Savings: ${scan_data['total_saving']:.2f}", border=1, align='C', fill=True)
    pdf.cell(5)
    pdf.set_text_color(0, 123, 255) # Blue
    pdf.cell(col_width, 20, f"Health Score: {scan_data['optimization_score']}%", border=1, align='C', fill=True)
    pdf.ln(25)
    
    pdf.set_text_color(100, 100, 100)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.cell(0, 5, f"* Live Run-Rate (via AWS Pricing API): ${scan_data.get('total_cost', 0):.2f}/mo", ln=True)
    pdf.ln(10)
    
    pdf.set_text_color(35, 47, 62)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, "Top Optimization Recommendations", ln=True)
    pdf.ln(5)
    
    # Recommendations Table
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_fill_color(230, 230, 230)
    
    headers = ["Service", "Resource ID", "Action", "Monthly Saving", "Priority"]
    widths = [30, 50, 60, 30, 20]
    
    for i in range(len(headers)):
        pdf.cell(widths[i], 10, headers[i], border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_font('Helvetica', '', 9)
    for rec in advice_data.get('recommendations', []):
        # Auto-wrap row height
        pdf.cell(widths[0], 10, rec['service'], border=1)
        pdf.cell(widths[1], 10, str(rec['resource_id'])[:25], border=1)
        pdf.cell(widths[2], 10, rec['action'][:35], border=1)
        pdf.cell(widths[3], 10, f"${rec['monthly_saving']:.2f}", border=1, align='R')
        
        priority = rec['priority']
        if priority == 'HIGH': pdf.set_text_color(220, 53, 69)
        elif priority == 'MEDIUM': pdf.set_text_color(255, 193, 7)
        else: pdf.set_text_color(40, 167, 69)
        
        pdf.cell(widths[4], 10, priority, border=1, align='C')
        pdf.set_text_color(0, 0, 0)
        pdf.ln()

    # Visualizations Section
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_text_color(35, 47, 62)
    pdf.cell(0, 10, "Cost Analysis Visualizations", ln=True)
    pdf.ln(5)

    summary = scan_data.get('summary', {})
    services = []
    costs = []
    savings = []

    for svc, details in summary.items():
        if details.get('total_cost', 0) > 0 or details.get('total_saving', 0) > 0:
            services.append(svc)
            costs.append(details.get('total_cost', 0))
            savings.append(details.get('total_saving', 0))

    if services:
        import uuid
        import numpy as np

        # Set modern styling
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except Exception:
            plt.style.use('ggplot')

        chart_dir = tempfile.gettempdir()
        cost_img = os.path.join(chart_dir, f"cost_{uuid.uuid4().hex}.png")
        save_img = os.path.join(chart_dir, f"save_{uuid.uuid4().hex}.png")

        # 1. Cost Breakdown Data preparation
        cost_data = [(s, c) for s, c in zip(services, costs) if c > 0]
        cost_data.sort(key=lambda x: x[1], reverse=True)
        sc_services = [x[0] for x in cost_data]
        sc_costs = [x[1] for x in cost_data]

        if sc_costs:
            fig1, ax1 = plt.subplots(figsize=(8, 4))
            y_pos = np.arange(len(sc_services))
            bars = ax1.barh(y_pos, sc_costs, color='#2b6cb0', edgecolor='none')
            ax1.set_yticks(y_pos)
            ax1.set_yticklabels(sc_services, fontsize=11, fontweight='bold', color='#2d3748')
            ax1.invert_yaxis()
            ax1.set_xlabel('Monthly Cost ($)', fontsize=11, fontweight='bold', color='#4a5568')
            ax1.set_title('Monthly Cost Breakdown by Service', fontsize=14, fontweight='bold', pad=15, color='#1a202c')
            
            # Label bars
            max_val = max(sc_costs)
            for bar in bars:
                width = bar.get_width()
                if width > 0:
                    ax1.text(width + (max_val*0.01), bar.get_y() + bar.get_height()/2.,
                             f'${width:.2f}', ha='left', va='center', fontsize=10, color='#2b6cb0', fontweight='bold')
            ax1.spines['top'].set_visible(False)
            ax1.spines['right'].set_visible(False)
            ax1.spines['bottom'].set_color('#e2e8f0')
            ax1.spines['left'].set_color('#e2e8f0')
            plt.tight_layout()
            plt.savefig(cost_img, dpi=200, bbox_inches='tight', transparent=True)
            plt.close(fig1)

            # Insert to PDF and manage spacing accurately
            pdf.image(cost_img, x=15, y=pdf.get_y(), w=180)
            pdf.ln(95)

        # 2. Potential Savings Data preparation
        save_data = [(s, sv) for s, sv in zip(services, savings) if sv > 0]
        save_data.sort(key=lambda x: x[1], reverse=True)
        ss_services = [x[0] for x in save_data]
        ss_savings = [x[1] for x in save_data]

        if ss_savings:
            fig2, ax2 = plt.subplots(figsize=(8, 4))
            y_pos2 = np.arange(len(ss_services))
            bars2 = ax2.barh(y_pos2, ss_savings, color='#38a169', edgecolor='none')
            ax2.set_yticks(y_pos2)
            ax2.set_yticklabels(ss_services, fontsize=11, fontweight='bold', color='#2d3748')
            ax2.invert_yaxis()
            ax2.set_xlabel('Monthly Savings ($)', fontsize=11, fontweight='bold', color='#4a5568')
            ax2.set_title('Potential Savings by Service', fontsize=14, fontweight='bold', pad=15, color='#1a202c')
            
            max_val2 = max(ss_savings)
            for bar in bars2:
                width = bar.get_width()
                if width > 0:
                    ax2.text(width + (max_val2*0.01), bar.get_y() + bar.get_height()/2.,
                             f'${width:.2f}', ha='left', va='center', fontsize=10, color='#38a169', fontweight='bold')
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            ax2.spines['bottom'].set_color('#e2e8f0')
            ax2.spines['left'].set_color('#e2e8f0')
            plt.tight_layout()
            plt.savefig(save_img, dpi=200, bbox_inches='tight', transparent=True)
            plt.close(fig2)

            pdf.image(save_img, x=15, y=pdf.get_y(), w=180)
            pdf.ln(95)

        # Cleanup
        if os.path.exists(cost_img):
            os.remove(cost_img)
        if os.path.exists(save_img):
            os.remove(save_img)

    # Detailed Resources Table
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, "Detailed Resource Cost Inventory", ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.write(5, "Comprehensive list of scanned resources and their individual financial impact.")
    pdf.ln(10)

    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(35, 47, 62)
    pdf.set_text_color(255, 255, 255)
    
    det_headers = ["Service", "Resource Name/ID", "State/Type", "Monthly Cost ($)"]
    det_widths = [30, 80, 45, 35]
    
    for i in range(len(det_headers)):
        pdf.cell(det_widths[i], 10, det_headers[i], border=1, fill=True, align='C')
    pdf.ln()

    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(0, 0, 0)
    
    resources = scan_data.get('resources', [])
    for res in sorted(resources, key=lambda x: x.get('monthly_cost', 0), reverse=True):
        # Stop printing if we generated too many pages to avoid excessive length (limit ~100 items max in PDF)
        if pdf.page_no() > 10:
            pdf.cell(0, 10, "... Truncated for brevity. See dashboard for full list.", border=0, align='C')
            break
            
        svc = str(res.get('service', ''))[:15]
        res_name = str(res.get('name', res.get('resource_id', '')))[:45]
        
        state_type = f"{res.get('type','')} ({res.get('state','')})"
        cost_val = f"${res.get('monthly_cost', 0):.2f}"
        
        pdf.cell(det_widths[0], 8, svc, border=1)
        pdf.cell(det_widths[1], 8, res_name, border=1)
        pdf.cell(det_widths[2], 8, state_type[:22], border=1)
        pdf.cell(det_widths[3], 8, cost_val, border=1, align='R')
        pdf.ln()

    return pdf.output()

def generate_housekeeping_report(findings, remediations, profile, region):
    pdf = AWSReport()
    pdf.report_title = "AWS Housekeeping & Remediation Report"
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Report Context
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, f"Profile: {profile} | Region: {region}", ln=True)
    pdf.ln(10)
    
    # Comparison Table: Engineer's Decision Skill
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, "Engineer's Decision Skill Log (Post-Remediation)", ln=True)
    pdf.set_font('Helvetica', '', 10)
    pdf.write(5, "This table showcases the expert decisions made by the engineer to remediate infrastructure risks and optimize health.")
    pdf.ln(10)
    
    # Table Headers
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(35, 47, 62)
    pdf.set_text_color(255, 255, 255)
    
    headers = ["Resource", "Issue Detected", "Decision/Remediation", "Result"]
    widths = [45, 55, 60, 30]
    
    for i in range(len(headers)):
        pdf.cell(widths[i], 10, headers[i], border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(0, 0, 0)
    
    # Match remediations to findings
    # remediations is a list of { title, resource_id, status, steps }
    for rem in remediations:
        rid = rem.get('resource_id', 'N/A')
        title = rem.get('title', 'N/A')
        status = rem.get('status', 'N/A')
        
        # Determine the action description from the remediation steps or title
        action = title.replace("Check", "Remediate")
        
        pdf.cell(widths[0], 10, str(rid)[:22], border=1)
        pdf.cell(widths[1], 10, str(title)[:30], border=1)
        pdf.cell(widths[2], 10, str(action)[:35], border=1)
        
        if status == 'success': 
            pdf.set_text_color(40, 167, 69)
            pdf.cell(widths[3], 10, "REMEDIATED", border=1, align='C')
        else:
            pdf.set_text_color(220, 53, 69)
            pdf.cell(widths[3], 10, "FAILED/MANUAL", border=1, align='C')
        
        pdf.set_text_color(0, 0, 0)
        pdf.ln()

    # Remaining Findings Section (if any)
    if findings:
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, "Remaining Infrastructure Findings", ln=True)
        pdf.ln(5)
        
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_fill_color(230, 230, 230)
        headers = ["Category", "Severity", "Finding Title", "Recommended Action"]
        widths = [25, 20, 70, 75]
        for i in range(len(headers)):
            pdf.cell(widths[i], 10, headers[i], border=1, fill=True, align='C')
        pdf.ln()
        
        pdf.set_font('Helvetica', '', 8)
        for f in findings:
            # Check if this finding was already listed in remediations
            if any(r['resource_id'] == f['resource_id'] and r['title'] == f['title'] for r in remediations):
                continue
                
            pdf.cell(widths[0], 10, f['category'], border=1)
            
            sev = f['severity']
            if sev == 'HIGH': pdf.set_text_color(220, 53, 69)
            elif sev == 'MEDIUM': pdf.set_text_color(255, 193, 7)
            else: pdf.set_text_color(100, 100, 100)
            
            pdf.cell(widths[1], 10, sev, border=1, align='C')
            pdf.set_text_color(0, 0, 0)
            pdf.cell(widths[2], 10, f['title'][:40], border=1)
            pdf.cell(widths[3], 10, f['action'][:45], border=1)
            pdf.ln()

    return pdf.output()
