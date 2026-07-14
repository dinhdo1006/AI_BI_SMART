/** Gợi ý câu hỏi theo domain — dùng chung Sidebar + EmptyHero. */
export const DOMAIN_PROMPTS: Record<string, string[]> = {
  finance_vnfdata: [
    "Top 10 mã vốn hóa lớn nhất",
    "Diễn biến giá FPT 20 phiên gần nhất",
    "Dự báo xu hướng giá VCB theo dữ liệu gần đây",
    "So sánh P/E P/B ROE của FPT, VCB, HPG",
  ],
};

export function promptsForDomain(domainId: string): string[] {
  return DOMAIN_PROMPTS[domainId] || DOMAIN_PROMPTS.finance_vnfdata;
}
