import { useEffect, useState } from "react";
import { fetchLatestData } from "../services/api";
import SensorCard from "../components/SensorCard";

export default function Dashboard() {
    const [data, setData] = useState(null);

    useEffect(() => {
        fetchLatestData().then(res => {
            setData(res.data[0]);
        });
    }, []);

    if (!data) return <p>Loading...</p>;

    return (
        <div>
            <h1>Air Quality Dashboard</h1>
            <SensorCard label="Temperature" value={data.temperature} unit="°C" />
            <SensorCard label="Humidity" value={data.humidity} unit="%" />
            <SensorCard label="CO" value={data.co} unit="ppm" />
            <SensorCard label="MQ135" value={data.mq135} unit="ppm" />
            <SensorCard label="PM2.5" value={data.pm25} unit="µg/m³" />
        </div>
    );
}