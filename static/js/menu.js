// menu.js
Vue.createApp({
  data() {
    return {
      sidebarVisible: false,
      trendingList: [], // 인기 검색어 리스트를 저장할 배열
      trendingDate: "",
    };
  },
  mounted() {
    // 컴포넌트가 마운트된 후 인기 검색어를 가져오기 위해 fetchTrendingSearch 호출
    this.fetchTrendingSearch();
    this.updateTrendingDate();
    setInterval(() => {
      this.updateTrendingDate();
    }, 60000);
  },
  methods: {
    toggleSidebar() {
      this.sidebarVisible = !this.sidebarVisible;
    },
    selectTag(tagName) {
      window.location.href = '/index?tag=' + encodeURIComponent(tagName);
    },
    fetchTrendingSearch() {
      fetch('/api/trending-search')
        .then(response => response.json())
        .then(data => {
          this.trendingList = data.top_search;
        })
        .catch(err => {
          console.error('인기급상승 검색어 가져오는 중 오류:', err);
        });
    },
    updateTrendingDate() {
      const now = new Date();
      const days = ["일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"];
      const dayName = days[now.getDay()];
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, "0");
      const date = String(now.getDate()).padStart(2, "0");
    
      // 시간과 오전/오후 계산
      const rawHours = now.getHours();
      const period = rawHours >= 12 ? "오후" : "오전";
      const hours = String(rawHours % 12 || 12).padStart(2, "0"); // 12시간제 (0은 12로 표시)
      const minutes = String(now.getMinutes()).padStart(2, "0");
    
      // 트렌딩 날짜 설정
      this.trendingDate = `${year}년 ${month}월 ${date}일 ${dayName} ${period} ${hours}:${minutes}`;
      console.log("Trending Date Updated:", this.trendingDate);
    },
    
  },
}).mount("#menu");
