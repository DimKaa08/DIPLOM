import axios from 'axios';

export const searchTracks = async (query) => {
  // Достаем токен, который вы сохранили в LocalStorage при авторизации
  const token = localStorage.getItem('token'); 

  const response = await axios.get(`http://127.0.0.1:8000/search`, {
    params: { q: query },
    headers: {
      // Ключевое слово Bearer и пробел после него обязательны!
      Authorization: `Bearer ${token}` 
    }
  });
  return response.data;
};