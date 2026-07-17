import { BasicQuestionnaire } from './auth';

export const emptyQuestionnaire: BasicQuestionnaire = {
  fullName: '', gender: '', birthDate: '', residence: '', occupation: '', interests: ['', '', ''],
  mbti: '', favoriteColor: '', favoriteMusic: '', belief: '',
};

export const mbtiOptions = ['INTJ', 'INTP', 'ENTJ', 'ENTP', 'INFJ', 'INFP', 'ENFJ', 'ENFP', 'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ', 'ISTP', 'ISFP', 'ESTP', 'ESFP'];
