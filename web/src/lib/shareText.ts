// 공유 문구는 용도별로 나눈다. 메모, 선택, 선택 프로필, 방 정보는 넣지 않는다.
export const SITE_URL = "https://dowonpact.com";

export const inviteShare = (url: string): ShareData => ({
  title: "도원결의",
  text: "여행 전에 같은 상황에 각자 답해 주세요.",
  url,
});

export const serviceShare: ShareData = {
  title: "도원결의",
  text: "떠나기 전에, 서로의 마음을 한 장에. 동행과 같은 상황에 각자 답하고 추천 협약서를 받아 보세요.",
  url: SITE_URL,
};

export const resultShare: ShareData = {
  title: "여행 동행 협약서",
  text: "도원결의에서 받은 추천 협약서예요. 동행 모두가 정한 약속은 아니에요.",
};
