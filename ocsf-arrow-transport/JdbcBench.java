// Native-JVM JDBC fetch baseline for the Arrow transport benchmark.
// Fetches the same parquet result set row-by-row through DuckDB's JDBC driver, materializing every
// column value, with no Python/JPype bridge — so the elapsed is the honest row-oriented transport cost
// in its native runtime. Args: <parquet-path> [warmup] [trials]. Prints the median wall-clock ms.
// Run with the single-file source launcher (no javac needed):
//   java -cp .jars/duckdb_jdbc.jar ocsf-arrow-transport/JdbcBench.java <parquet> 1 3
import java.sql.*;
import java.util.Arrays;

public class JdbcBench {
    public static void main(String[] args) throws Exception {
        String pq = args[0];
        int warmup = args.length > 1 ? Integer.parseInt(args[1]) : 1;
        int trials = args.length > 2 ? Integer.parseInt(args[2]) : 3;
        Class.forName("org.duckdb.DuckDBDriver");
        long[] times = new long[trials];
        for (int r = 0; r < warmup + trials; r++) {
            long t0 = System.nanoTime();
            long rows = 0, acc = 0;
            try (Connection c = DriverManager.getConnection("jdbc:duckdb:");
                 Statement s = c.createStatement();
                 ResultSet rs = s.executeQuery("SELECT * FROM read_parquet('" + pq + "')")) {
                int cols = rs.getMetaData().getColumnCount();
                while (rs.next()) {
                    for (int i = 1; i <= cols; i++) {       // materialize every value (the row tax)
                        Object o = rs.getObject(i);
                        if (o != null) acc += o.hashCode();
                    }
                    rows++;
                }
            }
            long dt = (System.nanoTime() - t0) / 1_000_000;
            if (r >= warmup) times[r - warmup] = dt;
            System.err.println("run " + r + " rows=" + rows + " ms=" + dt + " acc=" + acc);
        }
        Arrays.sort(times);
        System.out.println(times[times.length / 2]);          // median ms to stdout
    }
}
