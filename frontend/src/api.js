const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export async function searchArticles(query, source = null) {
  try {
    const response = await fetch(`${API_BASE_URL}/rag_search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query, top_k: 20, source }), // Increased top_k for better coverage
    });
    if (!response.ok) throw new Error("Search failed");
    return await response.json();
  } catch (error) {
    console.error(error);
    return [];
  }
}

export async function searchSql(keyword, start_date = null, end_date = null, source = null) {
  try {
    const response = await fetch(`${API_BASE_URL}/sql_search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ 
        keyword, 
        start_date, 
        end_date,
        source,
        limit: 50 // Increase limit for SQL search to show more results
      }), 
    });
    if (!response.ok) throw new Error("SQL Search failed");
    return await response.json();
  } catch (error) {
    console.error(error);
    return [];
  }
}

export async function getArticleDetail(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/article/${id}`);
    if (!response.ok) throw new Error("Fetch detail failed");
    return await response.json();
  } catch (error) {
    console.error(error);
    return null;
  }
}

export async function summarizeArticle(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/summarize_article/${id}`);
    if (!response.ok) throw new Error("Summary generation failed");
    return await response.json();
  } catch (error) {
    console.error(error);
    return null;
  }
}

export async function travelTimeMachine(date = null) {
  try {
    const url = date ? `${API_BASE_URL}/time_machine?date=${date}` : `${API_BASE_URL}/time_machine`;
    const response = await fetch(url);
    if (!response.ok) throw new Error("Time machine failed");
    return await response.json();
  } catch (error) {
    console.error(error);
    return null;
  }
}