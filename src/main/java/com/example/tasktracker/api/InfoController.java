package com.example.tasktracker.api;

import com.example.tasktracker.service.TaskService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** Служебная точка входа: по ней удобно проверять, что контейнер поднялся. */
@RestController
@RequestMapping("/api/info")
public class InfoController {

    private final TaskService taskService;
    private final String version;

    public InfoController(TaskService taskService, @Value("${app.version}") String version) {
        this.taskService = taskService;
        this.version = version;
    }

    @GetMapping
    public Map<String, Object> info() {
        return Map.of(
                "application", "task-tracker",
                "version", version,
                "javaVersion", System.getProperty("java.version"),
                "tasksInStore", taskService.count()
        );
    }
}
