import axios from "axios";

const API = "http://localhost:8000";

export async function login(email, password) {
  const form = new FormData();
  form.append("username", email);
  form.append("password", password);

  const res = await axios.post(`${API}/auth/login`, form);
  return res.data;
}

export async function register(email, password) {
  const res = await axios.post(`${API}/auth/register`, null, {
    params: { email, password }
  });
  return res.data;
}
