import { Link, Route, Routes, useNavigate } from "react-router-dom";
import { Header } from "./components/ui";
import { BackProvider, useHeaderBack } from "./lib/back";
import { MockBar } from "./mock/MockBar";
import { Answer } from "./pages/Answer";
import { CreateRoom } from "./pages/CreateRoom";
import { Created } from "./pages/Created";
import { Landing } from "./pages/Landing";
import { Privacy } from "./pages/Privacy";
import { Result } from "./pages/Result";
import { RoomEntry } from "./pages/RoomEntry";
import { Wait } from "./pages/Wait";

const MOCK = import.meta.env.VITE_MOCK === "1";

function NotFound() {
  const navigate = useNavigate();
  useHeaderBack(() => navigate("/"));
  return (
    <main className="page">
      <h1 className="t-headline-lg">페이지를 찾지 못했어요</h1>
      <Link className="btn-text" to="/">
        처음 화면으로
      </Link>
    </main>
  );
}

export function App() {
  return (
    <BackProvider>
      {MOCK && <MockBar />}
      <Header />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/new" element={<CreateRoom />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/r/:code" element={<RoomEntry />} />
        <Route path="/r/:code/created" element={<Created />} />
        <Route path="/r/:code/answer" element={<Answer />} />
        <Route path="/r/:code/wait" element={<Wait />} />
        <Route path="/r/:code/result" element={<Result />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BackProvider>
  );
}
