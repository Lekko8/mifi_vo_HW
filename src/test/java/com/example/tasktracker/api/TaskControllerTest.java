package com.example.tasktracker.api;

import com.example.tasktracker.service.TaskService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
class TaskControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private TaskService taskService;

    @BeforeEach
    void cleanStore() {
        taskService.deleteAll();
    }

    @Test
    @DisplayName("POST /api/tasks creates a task")
    void createTask() throws Exception {
        mockMvc.perform(post("/api/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"prepare CI pipeline\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").isNumber())
                .andExpect(jsonPath("$.title").value("prepare CI pipeline"))
                .andExpect(jsonPath("$.done").value(false));
    }

    @Test
    @DisplayName("GET /api/tasks returns stored tasks")
    void listTasks() throws Exception {
        taskService.create("first task");
        taskService.create("second task");

        mockMvc.perform(get("/api/tasks"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(2)))
                .andExpect(jsonPath("$[0].title").value("first task"));
    }

    @Test
    @DisplayName("PATCH /api/tasks/{id} marks task as done")
    void patchTask() throws Exception {
        long id = taskService.create("build docker image").id();

        mockMvc.perform(patch("/api/tasks/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"done\":true}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.done").value(true));
    }

    @Test
    @DisplayName("DELETE /api/tasks/{id} returns 204")
    void deleteTask() throws Exception {
        long id = taskService.create("temporary task").id();

        mockMvc.perform(delete("/api/tasks/" + id))
                .andExpect(status().isNoContent());
    }

    @Test
    @DisplayName("GET /api/tasks/{id} returns 404 for unknown id")
    void taskNotFound() throws Exception {
        mockMvc.perform(get("/api/tasks/9999"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.detail").value("Task with id 9999 was not found"));
    }

    @Test
    @DisplayName("POST /api/tasks returns 400 for blank title")
    void blankTitleIsRejected() throws Exception {
        mockMvc.perform(post("/api/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"  \"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("GET /actuator/health reports UP")
    void healthEndpoint() throws Exception {
        mockMvc.perform(get("/actuator/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"));
    }
}
